from .models import db, MonsterCatalog

INITIAL_MONSTERS = [
    {"id": 1, "name": "Sproutpaw", "element": "Grass", "power": 2, "hp": 2, "image_url": "/assets/monsters/Monster%20collection_1.jpeg"},
    {"id": 2, "name": "Vineclaw", "element": "Grass", "power": 4, "hp": 3, "image_url": "/assets/monsters/Monster%20collection_2.jpeg"},
    {"id": 3, "name": "Bramblebane", "element": "Grass", "power": 5, "hp": 6, "image_url": "/assets/monsters/Monster%20collection_3.jpeg"},
    {"id": 4, "name": "Mossbear", "element": "Grass", "power": 3, "hp": 5, "image_url": "/assets/monsters/Monster%20collection_4.jpeg"},
    {"id": 5, "name": "Drifin", "element": "Water", "power": 2, "hp": 3, "image_url": "/assets/monsters/Monster%20collection_5.jpeg"},
    {"id": 6, "name": "Tideglider", "element": "Water", "power": 4, "hp": 4, "image_url": "/assets/monsters/Monster%20collection_6.jpeg"},
    {"id": 7, "name": "Dolwhale", "element": "Water", "power": 6, "hp": 7, "image_url": "/assets/monsters/Monster%20collection_7.jpeg"},
    {"id": 8, "name": "Frosthart", "element": "Water", "power": 5, "hp": 5, "image_url": "/assets/monsters/Monster%20collection_8.jpeg"},
    {"id": 9, "name": "Emberbun", "element": "Fire", "power": 3, "hp": 2, "image_url": "/assets/monsters/Monster%20collection_9.jpeg"},
    {"id": 10, "name": "Blazetiger", "element": "Fire", "power": 5, "hp": 4, "image_url": "/assets/monsters/Monster%20collection_10.jpeg"},
    {"id": 11, "name": "Cindrake", "element": "Fire", "power": 7, "hp": 6, "image_url": "/assets/monsters/Monster%20collection_11.jpeg"},
    {"id": 12, "name": "Ashwing", "element": "Fire", "power": 3, "hp": 2, "image_url": "/assets/monsters/Monster%20collection_12.jpeg"},
    {"id": 13, "name": "Duskpaka", "element": "Dark", "power": 3, "hp": 5, "image_url": "/assets/monsters/Monster%20collection_13.jpeg"},
    {"id": 14, "name": "Colt", "element": "Dark", "power": 6, "hp": 3, "image_url": "/assets/monsters/Monster%20collection_14.jpeg"},
    {"id": 15, "name": "Budbug", "element": "Dark", "power": 2, "hp": 3, "image_url": "/assets/monsters/Monster%20collection_15.jpeg"},
    {"id": 16, "name": "Leaflark", "element": "Dark", "power": 4, "hp": 3, "image_url": "/assets/monsters/Monster%20collection_16.jpeg"},
]

STARTER_MONSTER_IDS = [1, 5, 9]

def init_catalog():
    if MonsterCatalog.query.count() == 0:
        for m in INITIAL_MONSTERS:
            db.session.add(MonsterCatalog(**m))
    else:
        for monster_data in INITIAL_MONSTERS:
            monster = db.session.get(MonsterCatalog, monster_data["id"])
            if monster and monster.image_url != monster_data["image_url"]:
                monster.image_url = monster_data["image_url"]
    db.session.commit()