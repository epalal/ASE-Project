"""Encounters: POST /encounters opens one (US-18)."""

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from . import rules
from .auth import require_player
from .errors import error
from .models import Challenge, Encounter, db
from .monster_client import MonsterServiceUnavailable
from .team import saved_team

encounters_bp = Blueprint("encounters", __name__)

MAX_ID = 2**31 - 1  # largest integer key the database stores


def _challenge_id_from(body):
    """Accept only {"challenge_id": <positive whole number>}; anything else is None."""
    if not isinstance(body, dict):
        return None
    challenge_id = body.get("challenge_id")
    if isinstance(challenge_id, bool) or not isinstance(challenge_id, int):
        return None
    if not 1 <= challenge_id <= MAX_ID:
        return None
    return challenge_id


def _as_json(encounter):
    return {
        "id": encounter.id,
        "status": encounter.status,
        "challenge_id": encounter.challenge_id,
        "wild": encounter.wild_snapshot,
        "team": encounter.team_snapshot,
        "team_power": encounter.team_power,
        "challenge_power": encounter.challenge_power,
        "p_win": encounter.p_win,
        "p_capture": encounter.p_capture,
    }


@encounters_bp.post("/encounters")
@require_player
def open_encounter():
    challenge_id = _challenge_id_from(request.get_json(silent=True))
    if challenge_id is None:
        return error("invalid_input", 'Send {"challenge_id": <challenge number>}.', 400)
    challenge = db.session.get(Challenge, challenge_id)
    if challenge is None:
        return error("challenge_not_found", "There is no challenge with this ID.", 404)
    monster_service = current_app.extensions["monster_client"]

    try:
        owned = {monster.id: monster for monster in monster_service.get_player_monsters(g.player_id)}
        wild = monster_service.get_species(challenge.wild_species_id)
    except MonsterServiceUnavailable:
        return error(
            "monster_service_unavailable",
            "Your monsters cannot be checked right now. Try again in a moment.",
            503,
        )
    team_ids = saved_team(g.player_id)
    try:
        rules.check_team(team_ids, owned_ids=owned.keys())
    except rules.TeamRuleError:
        return error("no_team", "Save a valid team of three monsters you own first.", 409)
    team = [owned[monster_id] for monster_id in team_ids]
    wild_owned = any(monster.species_id == wild.id for monster in owned.values())

    chances = rules.compute_chances(
        [rules.Monster(m.type, m.atk, m.hp) for m in team],
        rules.Monster(wild.type, wild.atk, wild.hp),
        wild_owned=wild_owned,
    )

    now = datetime.now(timezone.utc)
    previous = Encounter.query.filter_by(player_id=g.player_id, status="open").first()
    if previous is not None:  # one open encounter per player: the old one counts as an escape
        previous.status, previous.action, previous.result = "closed", "escape", "escaped"
        previous.closed_at = now
        db.session.flush()  # close it before the new one is inserted

    encounter = Encounter(
        id=str(uuid.uuid4()),
        player_id=g.player_id,
        challenge_id=challenge.id,
        status="open",
        team_snapshot=[asdict(monster) for monster in team],
        wild_snapshot={"species_id": wild.id, "name": wild.name, "type": wild.type, "atk": wild.atk, "hp": wild.hp},
        team_power=chances.team_power,
        challenge_power=chances.challenge_power,
        p_win=chances.p_win,
        p_capture=chances.p_capture,
        created_at=now,
    )
    db.session.add(encounter)
    db.session.commit()

    return jsonify(_as_json(encounter)), 201
