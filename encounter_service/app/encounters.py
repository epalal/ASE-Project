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


def _action_from(body):
    """Accept only {"action": <text>}; which actions exist is up to the rules."""
    if not isinstance(body, dict) or not isinstance(body.get("action"), str):
        return None
    return body["action"]


INVALID_ACTION = 'Send {"action": "attack"}, {"action": "capture"} or {"action": "escape"}.'


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
        "action": encounter.action,
        "roll": encounter.roll,
        "result": encounter.result,
        "reward_status": encounter.reward_status,
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

    # Rewards that could not be delivered earlier go first, so this fight uses the new stats.
    for waiting in Encounter.query.filter_by(player_id=g.player_id, reward_status="pending").all():
        _grant_reward(waiting)
    db.session.commit()

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
        reward_status="none",
        created_at=now,
    )
    db.session.add(encounter)
    db.session.commit()

    return jsonify(_as_json(encounter)), 201


@encounters_bp.post("/encounters/<encounter_id>/action")
@require_player
def choose_action(encounter_id):
    action = _action_from(request.get_json(silent=True))
    if action is None:
        return error("invalid_input", INVALID_ACTION, 400)
    encounter = db.session.get(Encounter, encounter_id)
    if encounter is None or encounter.player_id != g.player_id:  # 404 even if it exists: no hint for attackers
        return error("encounter_not_found", "There is no encounter with this ID.", 404)
    if encounter.status == "closed":
        return error("encounter_closed", "This encounter is already over.", 409)

    chances = rules.Chances(
        team_power=encounter.team_power,
        challenge_power=encounter.challenge_power,
        p_win=encounter.p_win,
        p_capture=encounter.p_capture,
    )
    try:
        outcome = rules.resolve(action, chances, draw=current_app.extensions["draw"])
    except rules.CaptureNotOffered:
        return error("capture_not_offered", "You already own this monster, so you cannot capture it.", 409)
    except rules.UnknownAction:
        return error("invalid_input", INVALID_ACTION, 400)

    encounter.status, encounter.action = "closed", action
    encounter.roll, encounter.result = outcome.roll, outcome.result
    encounter.closed_at = datetime.now(timezone.utc)

    if outcome.result in ("win", "captured"):
        _grant_reward(encounter)
    db.session.commit()

    return jsonify(_as_json(encounter))


def _grant_reward(encounter):
    """Ask the Monster Service for the reward (C10). If it cannot be reached,
    the result still counts and the reward stays pending, to be retried later;
    retrying is safe because the Monster Service rewards each encounter once."""
    monster_service = current_app.extensions["monster_client"]
    try:
        if encounter.result == "win":
            monster_service.grant_stats(
                encounter.id,
                encounter.player_id,
                [monster["id"] for monster in encounter.team_snapshot],
                rules.WIN_ATK_BONUS,
                rules.WIN_HP_BONUS,
            )
        else:
            monster_service.grant_capture(
                encounter.id, encounter.player_id, encounter.wild_snapshot["species_id"]
            )
    except MonsterServiceUnavailable:
        encounter.reward_status = "pending"
        return
    encounter.reward_status = "applied"
