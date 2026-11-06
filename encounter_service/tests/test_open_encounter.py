"""Opening an encounter (US-18), tested through the HTTP API."""

import pytest

SPROUTPAW, DRIFIN, EMBERBUN, BUDBUG = 1, 5, 9, 15  # catalogue IDs


def test_opening_an_encounter_shows_the_chances_for_the_saved_team(game):
    # Doc worked example: Sproutpaw, Drifin and Emberbun against a wild Emberbun
    # give team power 8, challenge power 7.5 and P(win) about 57%.
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])

    response = game.open("player-1", EMBERBUN)

    encounter = response.get_json()
    assert response.status_code == 201
    assert encounter["status"] == "open"
    assert encounter["wild"]["name"] == "Emberbun"
    assert [monster["name"] for monster in encounter["team"]] == ["Sproutpaw", "Drifin", "Emberbun"]
    assert encounter["team_power"] == 8
    assert encounter["challenge_power"] == 7.5
    assert encounter["p_win"] == pytest.approx(0.57, abs=0.005)
    assert encounter["p_capture"] is None  # the player already owns an Emberbun


def test_capture_is_offered_when_the_player_does_not_own_the_wild_monster(game):
    # Worked by hand: Drifin 2.5 - 1 (Grass beats Water) + Emberbun 2.5 + Budbug 2.5 + 1
    # (Dark beats Grass) = 7.5 against 3 x 2 = 6, so P(win) about 71% and P(capture) about 53%.
    game.give_team("player-1", [DRIFIN, EMBERBUN, BUDBUG])

    encounter = game.open("player-1", SPROUTPAW).get_json()

    assert encounter["team_power"] == 7.5
    assert encounter["p_win"] == pytest.approx(0.71, abs=0.005)
    assert encounter["p_capture"] == pytest.approx(0.53, abs=0.005)


def test_an_encounter_cannot_start_without_a_saved_team(game, monster_service):
    monster_service.give("player-1", "m1", "m2", "m3")  # owns monsters but never saved a team

    response = game.open("player-1", SPROUTPAW)

    assert response.status_code == 409
    assert response.get_json()["error"] == "no_team"


def test_an_encounter_cannot_start_when_a_team_monster_no_longer_exists(game, monster_service):
    sproutpaw, drifin, emberbun = game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])
    monster_service.forget("player-1", drifin)

    response = game.open("player-1", BUDBUG)

    assert response.status_code == 409
    assert response.get_json()["error"] == "no_team"


def test_opening_a_new_encounter_while_one_is_open_works(game):
    # The doc: one open encounter per player; opening a new one closes the old one as escaped.
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])
    first = game.open("player-1", BUDBUG)

    second = game.open("player-1", SPROUTPAW)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.get_json()["status"] == "open"
    assert second.get_json()["id"] != first.get_json()["id"]


def test_opening_an_encounter_while_the_monster_service_is_down_fails_cleanly(game, monster_service):
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])
    monster_service.go_down()

    response = game.open("player-1", BUDBUG)

    assert response.status_code == 502
    assert response.get_json()["error"] == "monster_service_unavailable"


def test_opening_an_encounter_while_the_monster_service_is_too_slow_times_out(game, monster_service):
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])
    monster_service.go_slow()

    response = game.open("player-1", BUDBUG)

    assert response.status_code == 504
    assert response.get_json()["error"] == "monster_service_timeout"


def test_a_challenge_that_does_not_exist_is_not_found(game):
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])

    response = game.open("player-1", 999)

    assert response.status_code == 404
    assert response.get_json()["error"] == "challenge_not_found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"challenge_id": "9"},
        {"challenge_id": True},
        {"challenge_id": 9.5},
        {"challenge_id": 0},
        {"challenge_id": 10**30},
        [9],
    ],
    ids=["no challenge_id", "text", "true", "decimal", "zero", "huge number", "list instead of object"],
)
def test_a_malformed_open_request_is_refused(client, token_for, game, body):
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])

    response = client.post("/encounters", json=body, headers=token_for("player-1"))

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"


def test_an_open_request_that_is_not_json_is_refused(client, token_for):
    response = client.post("/encounters", data="challenge 9", headers=token_for("player-1"))

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"


def test_opening_an_encounter_needs_a_login_token(client):
    response = client.post("/encounters", json={"challenge_id": 1})

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
