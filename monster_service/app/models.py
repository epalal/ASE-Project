import os
import base64
import hashlib
import hmac
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, String
from sqlalchemy import text
from sqlalchemy.orm import validates
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

db = SQLAlchemy()

@lru_cache(maxsize=8)
def _read_data_key(key_path):
    try:
        key = Path(key_path).read_bytes().strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read the Monster Service data key at {key_path}") from exc
    try:
        Fernet(key)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("The Monster Service data key is not a valid Fernet key") from exc
    return key

@lru_cache(maxsize=8)
def _fernet_for_key(key):
    return Fernet(key)

def _data_key():
    return _read_data_key(os.environ.get("DATA_KEY_PATH", "/run/secrets/data_key"))

def get_fernet():
    return _fernet_for_key(_data_key())

def player_id_lookup(player_id):
    key_material = base64.urlsafe_b64decode(_data_key())
    lookup_key = hmac.new(
        key_material,
        b"monster-service/player-id-lookup/v1",
        hashlib.sha256,
    ).digest()
    digest = hmac.new(lookup_key, player_id.encode("utf-8"), hashlib.sha256).digest()
    return f"h1_{digest[:24].hex()}"

def migrate_legacy_player_ids():
    migration_name = "encrypted-player-ids-v1"
    if db.session.get(ServiceMigration, migration_name):
        return

    cipher = get_fernet()
    rows = db.session.execute(
        text("SELECT id, player_id, secret_notes FROM player_monsters")
    ).mappings().all()
    for row in rows:
        stored_player_id = row["player_id"]
        stored_identity = row["secret_notes"]
        if stored_identity:
            try:
                decrypted_identity = cipher.decrypt(stored_identity.encode()).decode()
            except InvalidToken:
                decrypted_identity = None
            if (
                decrypted_identity is not None
                and hmac.compare_digest(
                    player_id_lookup(decrypted_identity),
                    stored_player_id,
                )
            ):
                continue

        encrypted_identity = cipher.encrypt(stored_player_id.encode()).decode()
        db.session.execute(
            text(
                "UPDATE player_monsters "
                "SET player_id = :lookup, secret_notes = :identity "
                "WHERE id = :id"
            ),
            {
                "lookup": player_id_lookup(stored_player_id),
                "identity": encrypted_identity,
                "id": row["id"],
            },
        )

    db.session.add(ServiceMigration(name=migration_name))
    db.session.commit()

class EncryptedField(TypeDecorator):
    """Encrypts sensitive fields on write and decrypts on read using Fernet."""
    impl = db.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return get_fernet().encrypt(value.encode()).decode()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return get_fernet().decrypt(value.encode()).decode()
        return value

class MonsterCatalog(db.Model):
    __tablename__ = 'monster_catalog'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    element = db.Column(db.String(20), nullable=False)  # Fire, Water, Dark, Grass
    power = db.Column(db.Integer, nullable=False)       # ATK = power
    hp = db.Column(db.Integer, nullable=False)          # HP
    image_url = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "element": self.element,
            "power": self.power,
            "hp": self.hp,
            "image_url": self.image_url
        }

class PlayerMonster(db.Model):
    __tablename__ = 'player_monsters'
    __table_args__ = (
        db.UniqueConstraint('player_id', 'monster_id', name='uq_player_monster'),
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_lookup = db.Column("player_id", db.String(64), nullable=False, index=True)
    player_id = db.Column("secret_notes", EncryptedField, nullable=False)
    monster_id = db.Column(db.Integer, db.ForeignKey('monster_catalog.id'), nullable=False)
    atk = db.Column(db.Integer, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
    acquired_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    monster = db.relationship('MonsterCatalog', lazy='joined')

    @validates("player_id")
    def set_player_id(self, key, value):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 64
            or not value.isprintable()
        ):
            raise ValueError("player_id must be a non-empty printable string of at most 64 characters")
        self.player_lookup = player_id_lookup(value)
        return value

    def to_dict(self):
        acquired = self.acquired_at
        if acquired.tzinfo is None:
            acquired = acquired.replace(tzinfo=timezone.utc)
        return {
            "ownership_id": self.id,
            "player_id": self.player_id,
            "acquired_at": acquired.astimezone(timezone.utc).isoformat(),
            "atk": self.atk,
            "hp": self.hp,
            "monster": self.monster.to_dict()
        }

class AppliedReward(db.Model):
    __tablename__ = 'applied_rewards'
    encounter_id = db.Column(db.String(64), primary_key=True)
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ServiceMigration(db.Model):
    __tablename__ = 'service_migrations'
    name = db.Column(db.String(100), primary_key=True)