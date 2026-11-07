"""Encounters: POST /encounters opens one (US-18), and
POST /encounters/{id}/action plays it with attack, capture or escape (US-19, US-21, US-22).
GET /encounters and GET /encounters/{id} are the player's history (US-23, US-24)."""

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from . import rules
from .auth import require_player
from .errors import error
from .models import Challenge, Encounter, db
from .monster_client import MonsterServiceUnavailable, RewardRefused
from .team import saved_team

encounters_bp = Blueprint("encounters", __name__)

MAX_DB_INTEGER = 2**31 - 1  # the largest integer the database column stores
INVALID_ACTION = 'Send {"action": "attack"}, {"action": "capture"} or {"action": "escape"}.'
HISTORY_LIMIT = 50  # the newest encounters only, so the answer stays small after thousands of games


def _challenge_id_from(body):
    """Accept only {"challenge_id": <positive whole number>}; anything else is None."""
    if not isinstance(body, dict):
        return None
    challenge_id = body.get("challenge_id")
    if isinstance(challenge_id, bool) or not isinstance(challenge_id, int):
        return None
    if not 1 <= challenge_id <= MAX_DB_INTEGER:
        return None
    return challenge_id


def _action_from(body):
    """Accept only {"action": <text>}; which actions exist is up to the rules."""
    if not isinstance(body, dict) or not isinstance(body.get("action"), str):
        return None
    return body["action"]


def _closing(action, outcome, at):
    """The column values that close an encounter."""
    return {"status": "closed", "action": action, "roll": outcome.roll, "result": outcome.result, "closed_at": at}


def _utc_text(moment):
    """ISO 8601 in UTC. SQLite gives the time back without its time zone, so it is added again."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def _as_json(encounter):
    return {
        "id": encounter.id,
        "status": encounter.status,
        "challenge_id": encounter.challenge_id,
        "wild": encounter.wild_snapshot,
        "team": encounter.team_snapshot,
        **asdict(encounter.chances),
        "action": encounter.action,
        "roll": encounter.roll,
        "result": encounter.result,
        "reward_status": encounter.reward_status,
        "created_at": _utc_text(encounter.created_at),
        "closed_at": _utc_text(encounter.closed_at),
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
    monster_client = current_app.extensions["monster_client"]

    # Rewards that could not be delivered earlier go first, so this fight uses the new stats.
    for waiting in Encounter.query.filter_by(player_id=g.player_id, reward_status="pending").all():
        _grant_reward(waiting)
    db.session.commit()

    owned = {monster.id: monster for monster in monster_client.get_player_monsters(g.player_id)}
    wild = monster_client.get_species(challenge.wild_species_id)
    team_ids = saved_team(g.player_id)
    try:
        rules.check_team(team_ids, owned_ids=owned.keys())
    except rules.TeamRuleError:
        return error("no_team", "Save a valid team of three monsters you own first.", 409)
    team = [owned[monster_id] for monster_id in team_ids]

    chances = rules.compute_chances(
        [rules.Monster(m.type, m.atk, m.hp) for m in team],
        rules.Monster(wild.type, wild.atk, wild.hp),
        wild_owned=any(monster.species_id == wild.id for monster in owned.values()),
    )

    now = datetime.now(timezone.utc)
    # One open encounter per player: an encounter still open counts as an escape.
    Encounter.query.filter_by(player_id=g.player_id, status="open").update(
        _closing("escape", rules.ESCAPED, at=now), synchronize_session=False
    )
    encounter = Encounter(
        id=str(uuid.uuid4()),
        player_id=g.player_id,
        challenge_id=challenge.id,
        status="open",
        team_snapshot=[asdict(monster) for monster in team],
        wild_snapshot={"species_id": wild.id, "name": wild.name, "type": wild.type, "atk": wild.atk, "hp": wild.hp},
        **asdict(chances),
        reward_status="none",
        created_at=now,
    )
    db.session.add(encounter)
    db.session.commit()

    return jsonify(_as_json(encounter)), 201


@encounters_bp.get("/encounters")
@require_player
def history():
    encounters = (
        Encounter.query.filter_by(player_id=g.player_id, status="closed")
        .order_by(Encounter.created_at.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )
    return jsonify(encounters=[_as_json(encounter) for encounter in encounters])


def _players_encounter(encounter_id):
    """The player's own encounter, or None. Another player's encounter counts as
    missing too, so the answer gives no hint about which IDs exist."""
    encounter = db.session.get(Encounter, encounter_id)
    if encounter is None or encounter.player_id != g.player_id:
        return None
    return encounter


def _encounter_not_found():
    return error("encounter_not_found", "There is no encounter with this ID.", 404)


@encounters_bp.get("/encounters/<encounter_id>")
@require_player
def show_encounter(encounter_id):
    encounter = _players_encounter(encounter_id)
    if encounter is None:
        return _encounter_not_found()
    return jsonify(_as_json(encounter))


@encounters_bp.post("/encounters/<encounter_id>/action")
@require_player
def choose_action(encounter_id):
    action = _action_from(request.get_json(silent=True))
    if action is None:
        return error("invalid_input", INVALID_ACTION, 400)
    encounter = _players_encounter(encounter_id)
    if encounter is None:
        return _encounter_not_found()
    if encounter.status == "closed":
        return error("encounter_closed", "This encounter is already over.", 409)

    try:
        outcome = rules.resolve(action, encounter.chances, draw=current_app.extensions["draw"])
    except rules.CaptureNotOffered:
        return error("capture_not_offered", "You already own this monster, so you cannot capture it.", 409)
    except rules.UnknownAction:
        return error("invalid_input", INVALID_ACTION, 400)

    # Claim the encounter in one atomic update that only succeeds while it is still
    # open, and save it before calling the Monster Service. A second request that
    # arrives meanwhile finds nothing to claim, so it can never be rewarded too.
    rewarded = outcome.result in rules.REWARDED_RESULTS
    claimed = Encounter.query.filter_by(id=encounter.id, status="open").update(
        {
            **_closing(action, outcome, at=datetime.now(timezone.utc)),
            "reward_status": "pending" if rewarded else "none",
        },
        synchronize_session=False,
    )
    db.session.commit()
    if not claimed:
        return error("encounter_closed", "This encounter is already over.", 409)

    if rewarded:
        _grant_reward(encounter)
        db.session.commit()

    return jsonify(_as_json(encounter))


def _grant_reward(encounter):
    """Ask the Monster Service for the reward (C10). If it cannot be reached, the
    result still counts and the reward stays pending, to be retried before the next
    encounter; retrying is safe because the Monster Service rewards each encounter
    once. If it refuses, the reward is marked failed and not retried."""
    monster_client = current_app.extensions["monster_client"]
    try:
        if encounter.result == "win":
            monster_client.grant_stats(
                encounter.id,
                encounter.player_id,
                encounter.team_monster_ids,
                rules.WIN_ATK_BONUS,
                rules.WIN_HP_BONUS,
            )
        elif encounter.result == "captured":
            monster_client.grant_capture(encounter.id, encounter.player_id, encounter.wild_species_id)
        else:
            return
    except MonsterServiceUnavailable:
        encounter.reward_status = "pending"
        return
    except RewardRefused:
        encounter.reward_status = "failed"
        return
    encounter.reward_status = "applied"
