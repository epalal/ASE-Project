"""Lab 11, THREAT_MODEL.md row 15 (denial of service): a player can open at most
10 encounters per minute, tested through the HTTP API."""

SPROUTPAW, DRIFIN, EMBERBUN = 1, 5, 9  # catalogue IDs
TEAM = [SPROUTPAW, DRIFIN, EMBERBUN]


def test_the_eleventh_encounter_within_a_minute_is_refused(game):
    game.give_team("player-1", TEAM)
    for _ in range(10):
        assert game.open("player-1", SPROUTPAW).status_code == 201

    response = game.open("player-1", SPROUTPAW)

    assert response.status_code == 429
    assert response.get_json()["error"] == "too_many_requests"


def test_after_a_minute_the_player_can_open_encounters_again(game, clock):
    game.give_team("player-1", TEAM)
    for _ in range(10):
        game.open("player-1", SPROUTPAW)
    assert game.open("player-1", SPROUTPAW).status_code == 429

    clock.advance(seconds=61)

    assert game.open("player-1", SPROUTPAW).status_code == 201
