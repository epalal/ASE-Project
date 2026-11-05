from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError
from ..models import db, MonsterCatalog, PlayerMonster
from ..initial_monsters import STARTER_MONSTER_IDS
from ..auth import require_jwt, require_internal_secret

monsters_bp = Blueprint('monsters', __name__)

def ensure_starter_monsters(player_id: str):
    """US-06 (Lazy Init): Assegna i 4 mostri iniziali al primo accesso alla collezione."""
    owned = PlayerMonster.query.filter_by(player_id=player_id).all()
    if not owned:
        new_monsters = []
        for m_id in STARTER_MONSTER_IDS:
            pm = PlayerMonster(player_id=player_id, monster_id=m_id)
            db.session.add(pm)
            new_monsters.append(pm)
        db.session.commit()
        return new_monsters
    return owned

# US-10: Catalogo completo dei 16 mostri
@monsters_bp.route('/monsters', methods=['GET'])
def get_catalog():
    monsters = MonsterCatalog.query.order_by(MonsterCatalog.id.asc()).all()
    return jsonify([m.to_dict() for m in monsters]), 200

# US-11: Dettagli e immagine di un singolo mostro
@monsters_bp.route('/monsters/<int:monster_id>', methods=['GET'])
def get_monster_detail(monster_id):
    if monster_id < 1 or monster_id > 16:
        return jsonify({"error": "ID mostro non valido (deve essere compreso tra 1 e 16)"}), 404
    monster = db.session.get(MonsterCatalog, monster_id)
    if not monster:
        return jsonify({"error": "Mostro non trovato"}), 404
    return jsonify(monster.to_dict()), 200

# US-06 & US-09: Collezione personale del giocatore (con Lazy Init)
@monsters_bp.route('/collection', methods=['GET'])
@require_jwt
def get_player_collection():
    player_id = g.player_id
    owned_monsters = ensure_starter_monsters(player_id)
    return jsonify({
        "player_id": player_id,
        "count": len(owned_monsters),
        "collection": [pm.to_dict() for pm in owned_monsters]
    }), 200

# US-12: Aggiunta mostro vinto/catturato (chiamato da Encounter Service)
@monsters_bp.route('/monsters/reward', methods=['POST'])
@require_internal_secret
def grant_reward():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Payload JSON mancante o malformato"}), 400
    
    player_id = str(data.get("player_id", "")).strip()
    monster_id = data.get("monster_id")
    encounter_id = str(data.get("encounter_id", "")).strip()

    if not player_id or not isinstance(monster_id, int) or isinstance(monster_id, bool) or not encounter_id:
        return jsonify({"error": "Campi obbligatori: player_id (str), monster_id (int), encounter_id (str)"}), 400

    catalog_monster = db.session.get(MonsterCatalog, monster_id)
    if not catalog_monster:
        return jsonify({"error": "Il monster_id specificato non esiste nel catalogo (1-16)"}), 404

    ensure_starter_monsters(player_id)

    existing_reward = PlayerMonster.query.filter_by(reward_encounter_id=encounter_id).first()
    if existing_reward:
        return jsonify({
            "message": "Ricompensa già erogata per questo encounter_id",
            "reward": existing_reward.to_dict()
        }), 200

    new_reward = PlayerMonster(
        player_id=player_id,
        monster_id=monster_id,
        reward_encounter_id=encounter_id
    )
    try:
        db.session.add(new_reward)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Conflitto di integrità nell'assegnazione della ricompensa"}), 409

    return jsonify({
        "message": "Mostro aggiunto alla collezione",
        "reward": new_reward.to_dict()
    }), 201