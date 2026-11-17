import os
import sys
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, String
from cryptography.fernet import Fernet

db = SQLAlchemy()


def get_fernet():
    key_path = os.environ.get("DATA_KEY_PATH", "/certs/data.key")
    try:
        with open(key_path, "r", encoding="ascii") as key_file:
            key = key_file.read().strip()
        return Fernet(key.encode("ascii"))
    except FileNotFoundError:
        if os.environ.get("TESTING") == "1" or "pytest" in sys.modules:
            return Fernet(Fernet.generate_key())
        raise RuntimeError(f"Required encryption key not found: {key_path}")


fernet = get_fernet()


class EncryptedField(TypeDecorator):
    """Encrypt the field on write and decrypt it on read."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return fernet.encrypt(value.encode()).decode()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return fernet.decrypt(value.encode()).decode()
        return value


class MonsterCatalog(db.Model):
    __tablename__ = 'monster_catalog'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    element = db.Column(db.String(20), nullable=False)
    power = db.Column(db.Integer, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
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
    player_id = db.Column(db.String(64), nullable=False, index=True)
    monster_id = db.Column(db.Integer, db.ForeignKey('monster_catalog.id'), nullable=False)
    atk = db.Column(db.Integer, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
    acquired_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    secret_notes = db.Column(EncryptedField, nullable=True, default="Protected sensible data")
    monster = db.relationship('MonsterCatalog', lazy='joined')

    def to_dict(self):
        return {
            "ownership_id": self.id,
            "player_id": self.player_id,
            "acquired_at": self.acquired_at.isoformat(),
            "atk": self.atk,
            "hp": self.hp,
            "monster": self.monster.to_dict(),
            "secret_notes": self.secret_notes
        }


class AppliedReward(db.Model):
    __tablename__ = 'applied_rewards'
    encounter_id = db.Column(db.String(64), primary_key=True)
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
