import json
import os
from flask import Blueprint, jsonify, request, g, send_from_directory, current_app
from sqlalchemy.exc import IntegrityError
from ..models import AppliedReward, db, MonsterCatalog, PlayerMonster, player_id_lookup
from ..initial_monsters import STARTER_MONSTER_IDS
from ..auth import require_jwt, require_internal_secret

monsters_bp = Blueprint('monsters', __name__)


def _error(code: str, message: str, status: int):
    return jsonify({"error": code, "message": message}), status


def _is_valid_id(value) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 64
        and value == value.strip()
        and value.isprintable()
    )


def _reject_json_constant(constant: str):
    raise ValueError(f"Unsupported JSON constant: {constant}")


def _parse_json_object():
    raw = request.get_data(as_text=True)
    if not raw:
        return None
    try:
        data = json.loads(raw, parse_constant=_reject_json_constant)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None

# US-06: Initialization of starter monsters for a player
def get_starter_monsters(player_id: str):
    player_lookup = player_id_lookup(player_id)
    owned = PlayerMonster.query.filter_by(player_lookup=player_lookup).all()
    if not owned:
        try:
            for m_id in STARTER_MONSTER_IDS:
                catalog_item = db.session.get(MonsterCatalog, m_id)
                if catalog_item:
                    pm = PlayerMonster(player_id=player_id, monster_id=m_id, atk=catalog_item.power, hp=catalog_item.hp)
                    db.session.add(pm)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        owned = PlayerMonster.query.filter_by(player_lookup=player_lookup).all()
    return owned

# US-10: Full catalog of monsters
@monsters_bp.route('/monsters', methods=['GET'])
def get_catalog():
    monsters = MonsterCatalog.query.order_by(MonsterCatalog.id.asc()).all()
    return jsonify([m.to_dict() for m in monsters]), 200

# US-11: Details and image of a single monster
@monsters_bp.route('/monsters/<int:monster_id>', methods=['GET'])
def get_monster_detail(monster_id):
    if monster_id < 1 or monster_id > 16:
        return _error("monster_not_found", "ID not valid (must be between 1 and 16)", 404)
    monster = db.session.get(MonsterCatalog, monster_id)
    if not monster:
        return _error("monster_not_found", "Monster not found", 404)
    return jsonify(monster.to_dict()), 200

# US-11: Serve monster images from the static assets directory (safer implementation for accessing images)
@monsters_bp.route('/assets/monsters/<path:filename>', methods=['GET'])
def serve_monster_images(filename):
    """Serve monster images from the static assets directory."""
    images_dir = os.path.join(current_app.root_path, 'static', 'assets', 'monsters')
    return send_from_directory(images_dir, filename)

# US-06 & US-09: Get player's monster collection
@monsters_bp.route('/collection', methods=['GET'])
@require_jwt
def get_player_collection():
    player_id = g.player_id
    owned_monsters = get_starter_monsters(player_id)
    return jsonify({
        "player_id": player_id,
        "count": len(owned_monsters),
        "collection": [pm.to_dict() for pm in owned_monsters]
    }), 200

# C9: Return the player's collection to the Encounter service
@monsters_bp.route('/internal/players/<player_id>/monsters', methods=['GET'])
@require_internal_secret
def get_player_monsters(player_id):
    if not _is_valid_id(player_id):
        return _error("invalid_input", "player_id must be 1 to 64 printable characters", 400)
    owned_monsters = get_starter_monsters(player_id)
    return jsonify({
        "player_id": player_id,
        "count": len(owned_monsters),
        "collection": [monster.to_dict() for monster in owned_monsters],
    }), 200

# C10: Apply encounter rewards from the Encounter service
@monsters_bp.route('/internal/rewards', methods=['POST'])
@require_internal_secret
def grant_reward():
    data = _parse_json_object()
    if data is None:
        return _error("invalid_input", "Request body must be a valid JSON object", 400)

    player_id = data.get("player_id")
    encounter_id = data.get("encounter_id")
    if not _is_valid_id(player_id) or not _is_valid_id(encounter_id):
        return _error(
            "invalid_input",
            "player_id and encounter_id must be 1 to 64 printable characters",
            400,
        )

    if db.session.get(AppliedReward, encounter_id):
        return jsonify({"message": "Reward for this encounter has already been granted"}), 200

    has_stats = "owned_monster_ids" in data
    has_capture = "captured_species_id" in data
    if has_stats == has_capture:
        return _error("invalid_input", "Specify either a stats reward or a capture reward", 400)

    get_starter_monsters(player_id)
    try:
        if has_stats:
            owned_ids = data["owned_monster_ids"]
            atk_bonus = data.get("atk_bonus", 0)
            hp_bonus = data.get("hp_bonus", 0)
            if (
                not isinstance(owned_ids, list)
                or not owned_ids
                or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in owned_ids)
                or not isinstance(atk_bonus, int)
                or isinstance(atk_bonus, bool)
                or not isinstance(hp_bonus, int)
                or isinstance(hp_bonus, bool)
                or atk_bonus < 0
                or hp_bonus < 0
            ):
                return _error("invalid_input", "Invalid stats reward payload", 400)

            owned_monsters = PlayerMonster.query.filter(
                PlayerMonster.player_lookup == player_id_lookup(player_id),
                PlayerMonster.id.in_(owned_ids),
            ).all()
            if len(owned_monsters) != len(set(owned_ids)):
                return _error("not_found", "One or more owned_monster_ids do not belong to player_id", 404)
            for owned_monster in owned_monsters:
                owned_monster.atk = min(owned_monster.atk + atk_bonus, owned_monster.monster.power + 3)
                owned_monster.hp = min(owned_monster.hp + hp_bonus, owned_monster.monster.hp + 3)
            db.session.add(AppliedReward(encounter_id=encounter_id))
            db.session.commit()
            return jsonify({
                "message": "Monster stats updated successfully",
                "updated_monsters": [monster.to_dict() for monster in owned_monsters],
            }), 200

        captured_species_id = data["captured_species_id"]
        if not isinstance(captured_species_id, int) or isinstance(captured_species_id, bool):
            return _error("invalid_input", "captured_species_id must be an integer", 400)
        catalog_monster = db.session.get(MonsterCatalog, captured_species_id)
        if not catalog_monster:
            return _error("not_found", "captured_species_id does not exist in the catalog", 404)
        if PlayerMonster.query.filter_by(
            player_lookup=player_id_lookup(player_id),
            monster_id=captured_species_id,
        ).first():
            return _error("already_owned", "Player already owns this species", 409)

        new_reward = PlayerMonster(
            player_id=player_id,
            monster_id=captured_species_id,
            atk=catalog_monster.power,
            hp=catalog_monster.hp,
        )
        db.session.add(new_reward)
        db.session.add(AppliedReward(encounter_id=encounter_id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.get(AppliedReward, encounter_id):
            return jsonify({"message": "Reward for this encounter has already been granted"}), 200
        return _error("conflict", "Conflict in reward assignment", 409)

    return jsonify({
        "message": "Monster reward granted successfully",
        "reward": new_reward.to_dict(),
    }), 201