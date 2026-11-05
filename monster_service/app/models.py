from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class MonsterCatalog(db.Model):
    __tablename__ = 'monster_catalog'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    element = db.Column(db.String(20), nullable=False)  # Fire, Water, Darkness, Earth
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
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_id = db.Column(db.String(64), nullable=False, index=True)
    monster_id = db.Column(db.Integer, db.ForeignKey('monster_catalog.id'), nullable=False)
    acquired_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reward_encounter_id = db.Column(db.String(64), unique=True, nullable=True)

    monster = db.relationship('MonsterCatalog', lazy='joined')

    def to_dict(self):
        return {
            "ownership_id": self.id,
            "player_id": self.player_id,
            "acquired_at": self.acquired_at.isoformat(),
            "monster": self.monster.to_dict()
        }