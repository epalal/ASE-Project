"""Team endpoints: GET /team and PUT /team (US-14, US-15, US-16)."""

import re

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_player
from .errors import error
from .models import TeamMember, db
from .rules import TeamRuleError, check_team

team_bp = Blueprint("team", __name__)

MAX_ID_LENGTH = 64  # matches the database column
_FLOAT_SPECIES_ID_RE = re.compile(r"^[1-9]\d*\.0$")


def _monster_ids_from(body):
    """Accept only {"monster_ids": [<text>, ...]}; anything else is None.
    An ID must be printable text (Lab 8): a control character is refused, not cleaned."""
    if not isinstance(body, dict):
        return None
    monster_ids = body.get("monster_ids")
    if not isinstance(monster_ids, list):
        return None
    if not all(isinstance(i, str) and 0 < len(i) <= MAX_ID_LENGTH and i.isprintable() for i in monster_ids):
        return None
    return monster_ids


def saved_team(player_id):
    """The owned monster IDs of the player's team, in slot order."""
    rows = TeamMember.query.filter_by(player_id=player_id).order_by(TeamMember.slot).all()
    return [row.owned_monster_id for row in rows]


@team_bp.get("/team")
@require_player
def get_team():
    return jsonify(monster_ids=saved_team(g.player_id))


def _resolve_chosen_monster_ids(chosen, monsters):
    """Map Godot float-formatted species IDs (e.g. '1.0') to ownership IDs when unambiguous."""
    owned_ids = {monster.id for monster in monsters}
    by_species = {}
    for monster in monsters:
        if monster.species_id in by_species:
            return chosen  # ambiguous species in test fixtures; keep exact IDs
        by_species[monster.species_id] = monster.id

    resolved = []
    for item in chosen:
        if item not in owned_ids and _FLOAT_SPECIES_ID_RE.match(item):
            species_id = int(item[:-2])
            if species_id in by_species:
                resolved.append(by_species[species_id])
                continue
        resolved.append(item)
    return resolved


@team_bp.put("/team")
@require_player
def put_team():
    chosen = _monster_ids_from(request.get_json(silent=True))
    if chosen is None:
        return error("invalid_input", 'Send {"monster_ids": [three monster IDs]}.', 400)

    monsters = current_app.extensions["monster_client"].get_player_monsters(g.player_id)
    resolved = _resolve_chosen_monster_ids(chosen, monsters)
    try:
        check_team(resolved, owned_ids={monster.id for monster in monsters})
    except TeamRuleError as broken:
        return error(broken.code, broken.message, 400)

    TeamMember.query.filter_by(player_id=g.player_id).delete()
    for slot, monster_id in enumerate(resolved, start=1):
        db.session.add(TeamMember(player_id=g.player_id, slot=slot, owned_monster_id=monster_id))
    db.session.commit()

    return jsonify(monster_ids=saved_team(g.player_id))
