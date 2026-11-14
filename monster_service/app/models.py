from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, String
from cryptography.fernet import Fernet

db = SQLAlchemy()

def get_fernet():
    try:
        with open("/run/secrets/data_key", "r") as f:
            key = f.read().strip()
        return Fernet(key.encode())
    except IOError:
        return Fernet(Fernet.generate_key())
fernet = get_fernet()

class EncryptedField(TypeDecorator):
    """Crittograph data in write and decrypt in read. This is a simple implementation and should be improved for production use."""
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
    player_id = db.Column(db.String(64), nullable=False, index=True)
    monster_id = db.Column(db.Integer, db.ForeignKey('monster_catalog.id'), nullable=False)
    atk = db.Column(db.Integer, nullable=False)
    hp = db.Column(db.Integer, nullable=False)
    acquired_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # secret_notes = db.Column(EncryptedField, nullable=True, default="Protected sensible data")
    monster = db.relationship('MonsterCatalog', lazy='joined')

    def to_dict(self):
        return {
            "ownership_id": self.id,
            "player_id": self.player_id,
            "acquired_at": self.acquired_at.isoformat(),
            "atk": self.atk,
            "hp": self.hp,
            "monster": self.monster.to_dict(),
            # "secret_notes": self.secret_notes
        }

class AppliedReward(db.Model):
    __tablename__ = 'applied_rewards'
    encounter_id = db.Column(db.String(64), primary_key=True)
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))