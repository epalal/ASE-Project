"""Team endpoints: GET /team and PUT /team (US-14, US-15, US-16)."""

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_player
from .errors import error
from .models import TeamMember, db
from .rules import TeamRuleError, check_team

team_bp = Blueprint("team", __name__)

MAX_ID_LENGTH = 64  # matches the database column


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
    rows = TeamMember.query.filter_by(player_id=str(player_id)).order_by(TeamMember.slot).all()
    return [row.owned_monster_id for row in rows]


@team_bp.get("/team")
@require_player
def get_team():
    return jsonify(monster_ids=saved_team(g.player_id))


@team_bp.put("/team")
@require_player
def put_team():
    chosen = _monster_ids_from(request.get_json(silent=True))
    if chosen is None:
        return error("invalid_input", 'Send {"monster_ids": [three monster IDs]}.', 400)

    monsters = current_app.extensions["monster_client"].get_player_monsters(g.player_id)
    try:
        check_team(chosen, owned_ids={monster.id for monster in monsters})
    except TeamRuleError as broken:
        return error(broken.code, broken.message, 400)

    TeamMember.query.filter_by(player_id=g.player_id).delete()
    for slot, monster_id in enumerate(chosen, start=1):
        db.session.add(TeamMember(player_id=g.player_id, slot=slot, owned_monster_id=monster_id))
    db.session.commit()

    return jsonify(monster_ids=saved_team(g.player_id))
