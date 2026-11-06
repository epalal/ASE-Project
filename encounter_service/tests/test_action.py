"""Choosing an action in an open encounter (US-19, US-21, US-22), tested through the HTTP API."""

import pytest

SPROUTPAW, DRIFIN, EMBERBUN, BUDBUG = 1, 5, 9, 15  # catalogue IDs

# The doc's worked example: this team against a wild Emberbun has P(win) about 57%.
# The player owns an Emberbun, so capture is not offered.
EXAMPLE_TEAM, EXAMPLE_WILD = [SPROUTPAW, DRIFIN, EMBERBUN], EMBERBUN

# Worked by hand: this team against a wild Sproutpaw, which the player does not
# own, has P(win) about 71% and P(capture) about 53%.
CAPTURE_TEAM, CAPTURE_WILD = [DRIFIN, EMBERBUN, BUDBUG], SPROUTPAW


def test_an_attack_that_wins_raises_the_team_stats(game, dice, monster_service):
    team = game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    dice.next_roll = 0.10  # lower than P(win)

    response = game.act("player-1", encounter["id"], "attack")

    outcome = response.get_json()
    assert response.status_code == 200
    assert (outcome["status"], outcome["action"], outcome["result"]) == ("closed", "attack", "win")
    assert outcome["roll"] == 0.10
    assert outcome["reward_status"] == "applied"
    assert monster_service.rewards == [
        {
            "kind": "stats",
            "encounter_id": encounter["id"],
            "player_id": "player-1",
            "owned_monster_ids": team,
            "atk_bonus": 1,
            "hp_bonus": 1,
        }
    ]


def test_an_attack_that_loses_gives_nothing(game, dice, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    dice.next_roll = 0.90  # higher than P(win)

    outcome = game.act("player-1", encounter["id"], "attack").get_json()

    assert (outcome["status"], outcome["result"], outcome["roll"]) == ("closed", "loss", 0.90)
    assert outcome["reward_status"] == "none"
    assert monster_service.rewards == []


def test_a_successful_capture_adds_the_wild_monster(game, dice, monster_service):
    game.give_team("player-1", CAPTURE_TEAM)
    encounter = game.open("player-1", CAPTURE_WILD).get_json()
    dice.next_roll = 0.20  # lower than P(capture)

    outcome = game.act("player-1", encounter["id"], "capture").get_json()

    assert (outcome["status"], outcome["action"], outcome["result"]) == ("closed", "capture", "captured")
    assert outcome["reward_status"] == "applied"
    assert monster_service.rewards == [
        {"kind": "capture", "encounter_id": encounter["id"], "player_id": "player-1", "species_id": SPROUTPAW}
    ]


def test_a_capture_that_misses_gives_nothing(game, dice, monster_service):
    game.give_team("player-1", CAPTURE_TEAM)
    encounter = game.open("player-1", CAPTURE_WILD).get_json()
    dice.next_roll = 0.60  # would win an attack (71%), but is above P(capture) (53%)

    outcome = game.act("player-1", encounter["id"], "capture").get_json()

    assert (outcome["status"], outcome["result"], outcome["reward_status"]) == ("closed", "failed", "none")
    assert monster_service.rewards == []


def test_capture_is_refused_when_not_offered_and_the_encounter_stays_open(game, dice):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()  # the player owns an Emberbun

    refused = game.act("player-1", encounter["id"], "capture")
    dice.next_roll = 0.10
    attack = game.act("player-1", encounter["id"], "attack")

    assert refused.status_code == 409
    assert refused.get_json()["error"] == "capture_not_offered"
    assert attack.get_json()["result"] == "win"  # the encounter was still open


def test_escape_always_works_and_gives_nothing(game, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()

    outcome = game.act("player-1", encounter["id"], "escape").get_json()

    assert (outcome["status"], outcome["action"], outcome["result"]) == ("closed", "escape", "escaped")
    assert outcome["roll"] is None
    assert outcome["reward_status"] == "none"
    assert monster_service.rewards == []


def test_a_finished_encounter_cannot_be_played_again(game, dice, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    dice.next_roll = 0.10
    game.act("player-1", encounter["id"], "attack")  # a win

    again = game.act("player-1", encounter["id"], "attack")

    assert again.status_code == 409
    assert again.get_json()["error"] == "encounter_closed"
    assert len(monster_service.rewards) == 1  # rewarded once only


def test_an_encounter_closed_by_opening_a_new_one_cannot_be_played(game):
    game.give_team("player-1", EXAMPLE_TEAM)
    old = game.open("player-1", EXAMPLE_WILD).get_json()
    game.open("player-1", BUDBUG)  # closes the old one as escaped

    response = game.act("player-1", old["id"], "attack")

    assert response.status_code == 409
    assert response.get_json()["error"] == "encounter_closed"


def test_a_player_cannot_play_someone_elses_encounter(game, dice, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    victims_encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    dice.next_roll = 0.10

    response = game.act("attacker", victims_encounter["id"], "attack")

    assert response.status_code == 404
    assert response.get_json()["error"] == "encounter_not_found"
    assert monster_service.rewards == []


def test_an_encounter_that_does_not_exist_is_not_found(game):
    response = game.act("player-1", "00000000-0000-0000-0000-000000000000", "attack")

    assert response.status_code == 404
    assert response.get_json()["error"] == "encounter_not_found"


@pytest.mark.parametrize(
    "body",
    [{}, {"action": "dance"}, {"action": 1}, {"action": "ATTACK"}, ["attack"]],
    ids=["no action", "unknown action", "number", "wrong capitals", "list instead of object"],
)
def test_a_malformed_action_is_refused_and_the_encounter_stays_open(
    client, token_for, game, dice, body
):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()

    refused = client.post(f"/encounters/{encounter['id']}/action", json=body, headers=token_for("player-1"))
    dice.next_roll = 0.10
    attack = game.act("player-1", encounter["id"], "attack")

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "invalid_input"
    assert attack.get_json()["result"] == "win"  # still open after the bad request


def test_an_action_that_is_not_json_is_refused(client, token_for, game):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()

    refused = client.post(f"/encounters/{encounter['id']}/action", data="attack", headers=token_for("player-1"))

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "invalid_input"


def test_a_win_is_kept_and_its_reward_waits_when_the_monster_service_is_down(game, dice, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    monster_service.go_down()
    dice.next_roll = 0.10

    response = game.act("player-1", encounter["id"], "attack")

    outcome = response.get_json()
    assert response.status_code == 200
    assert (outcome["result"], outcome["reward_status"]) == ("win", "pending")
    assert monster_service.rewards == []


def test_a_pending_reward_is_given_before_the_next_encounter_opens(game, dice, monster_service):
    team = game.give_team("player-1", EXAMPLE_TEAM)
    first = game.open("player-1", EXAMPLE_WILD).get_json()
    monster_service.go_down()
    dice.next_roll = 0.10
    game.act("player-1", first["id"], "attack")  # a win, reward pending
    monster_service.come_back()

    second = game.open("player-1", BUDBUG)

    assert second.status_code == 201
    assert monster_service.rewards == [
        {
            "kind": "stats",
            "encounter_id": first["id"],
            "player_id": "player-1",
            "owned_monster_ids": team,
            "atk_bonus": 1,
            "hp_bonus": 1,
        }
    ]


def test_choosing_an_action_needs_a_login_token(client):
    response = client.post("/encounters/any-encounter/action", json={"action": "attack"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
