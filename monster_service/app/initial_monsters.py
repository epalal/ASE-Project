from .models import db, MonsterCatalog

INITIAL_MONSTERS = [
    {"id": 1, "name": "Sproutpaw", "element": "Grass", "power": 2, "hp": 2, "image_url": "/assets/monsters/sproutpaw.png"},
    {"id": 2, "name": "Vineclaw", "element": "Grass", "power": 4, "hp": 3, "image_url": "/assets/monsters/vineclaw.png"},
    {"id": 3, "name": "Bramblebane", "element": "Grass", "power": 5, "hp": 6, "image_url": "/assets/monsters/bramblebane.png"},
    {"id": 4, "name": "Mossbear", "element": "Grass", "power": 3, "hp": 5, "image_url": "/assets/monsters/mossbear.png"},
    {"id": 5, "name": "Drifin", "element": "Water", "power": 2, "hp": 3, "image_url": "/assets/monsters/drifin.png"},
    {"id": 6, "name": "Tideglider", "element": "Water", "power": 4, "hp": 4, "image_url": "/assets/monsters/tideglider.png"},
    {"id": 7, "name": "Dolwhale", "element": "Water", "power": 6, "hp": 7, "image_url": "/assets/monsters/dolwhale.png"},
    {"id": 8, "name": "Frosthart", "element": "Water", "power": 5, "hp": 5, "image_url": "/assets/monsters/frosthart.png"},
    {"id": 9, "name": "Emberbun", "element": "Fire", "power": 3, "hp": 2, "image_url": "/assets/monsters/emberbun.png"},
    {"id": 10, "name": "Blazetiger", "element": "Fire", "power": 5, "hp": 4, "image_url": "/assets/monsters/blazetiger.png"},
    {"id": 11, "name": "Cindrake", "element": "Fire", "power": 7, "hp": 6, "image_url": "/assets/monsters/cindrake.png"},
    {"id": 12, "name": "Ashwing", "element": "Fire", "power": 3, "hp": 2, "image_url": "/assets/monsters/ashwing.png"},
    {"id": 13, "name": "Duskpaka", "element": "Dark", "power": 3, "hp": 5, "image_url": "/assets/monsters/duskpaka.png"},
    {"id": 14, "name": "Colt", "element": "Dark", "power": 6, "hp": 3, "image_url": "/assets/monsters/colt.png"},
    {"id": 15, "name": "Budbug", "element": "Dark", "power": 2, "hp": 3, "image_url": "/assets/monsters/budbug.png"},
    {"id": 16, "name": "Leaflark", "element": "Dark", "power": 4, "hp": 3, "image_url": "/assets/monsters/leaflark.png"},
]

STARTER_MONSTER_IDS = [1, 5, 9]

def seed_catalog():
    if MonsterCatalog.query.count() == 0:
        for m in INITIAL_MONSTERS:
            db.session.add(MonsterCatalog(**m))
        db.session.commit()