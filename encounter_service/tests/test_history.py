"""Encounter history: GET /encounters and GET /encounters/{id} (US-23, US-24),
tested through the HTTP API."""

import datetime as dt

SPROUTPAW, DRIFIN, EMBERBUN = 1, 5, 9  # catalogue IDs
TEAM = [SPROUTPAW, DRIFIN, EMBERBUN]


def _finished_encounter(game, player_id, challenge_id):
    encounter_id = game.open(player_id, challenge_id).get_json()["id"]
    game.act(player_id, encounter_id, "escape")
    return encounter_id


def test_the_history_lists_finished_encounters_newest_first(game):
    game.give_team("player-1", TEAM)
    first = _finished_encounter(game, "player-1", SPROUTPAW)
    second = _finished_encounter(game, "player-1", DRIFIN)

    response = game.history("player-1")

    assert response.status_code == 200
    assert [encounter["id"] for encounter in response.get_json()["encounters"]] == [second, first]


def _listed(game, player_id):
    return [encounter["id"] for encounter in game.history(player_id).get_json()["encounters"]]


def test_an_encounter_still_open_is_not_in_the_history(game):
    game.give_team("player-1", TEAM)
    finished = _finished_encounter(game, "player-1", SPROUTPAW)
    game.open("player-1", DRIFIN)

    assert _listed(game, "player-1") == [finished]


def test_a_player_never_sees_another_players_encounters(game):
    game.give_team("player-1", TEAM)
    game.give_team("player-2", TEAM)
    mine = _finished_encounter(game, "player-1", SPROUTPAW)
    _finished_encounter(game, "player-2", SPROUTPAW)

    assert _listed(game, "player-1") == [mine]


def test_the_history_keeps_only_the_50_newest_encounters(game):
    game.give_team("player-1", TEAM)
    oldest = _finished_encounter(game, "player-1", SPROUTPAW)
    newer = [_finished_encounter(game, "player-1", SPROUTPAW) for _ in range(50)]

    listed = _listed(game, "player-1")

    assert len(listed) == 50
    assert oldest not in listed
    assert listed[0] == newer[-1]


def test_one_encounter_can_be_read_while_open_and_after_it_ends(game):
    game.give_team("player-1", TEAM)
    encounter_id = game.open("player-1", SPROUTPAW).get_json()["id"]

    while_open = game.show("player-1", encounter_id)
    game.act("player-1", encounter_id, "escape")
    after = game.show("player-1", encounter_id).get_json()

    assert while_open.status_code == 200
    assert (while_open.get_json()["id"], while_open.get_json()["status"]) == (encounter_id, "open")
    assert (after["status"], after["action"], after["result"]) == ("closed", "escape", "escaped")


def test_another_players_encounter_and_an_unknown_one_look_the_same(game):
    game.give_team("player-1", TEAM)
    theirs = _finished_encounter(game, "player-1", SPROUTPAW)

    for response in (game.show("player-2", theirs), game.show("player-2", "no-such-encounter")):
        assert response.status_code == 404
        assert response.get_json()["error"] == "encounter_not_found"


def _moment(text):
    moment = dt.datetime.fromisoformat(text)
    assert moment.utcoffset() == dt.timedelta(0)  # always in UTC
    return moment


def test_every_encounter_answer_says_when_it_opened_and_when_it_ended(game):
    game.give_team("player-1", TEAM)
    before = dt.datetime.now(dt.timezone.utc)
    opened = game.open("player-1", SPROUTPAW).get_json()
    ended = game.act("player-1", opened["id"], "escape").get_json()
    after = dt.datetime.now(dt.timezone.utc)
    listed = game.history("player-1").get_json()["encounters"][0]
    shown = game.show("player-1", opened["id"]).get_json()

    assert opened["closed_at"] is None
    assert before <= _moment(opened["created_at"]) <= _moment(ended["closed_at"]) <= after
    for answer in (ended, listed, shown):
        assert _moment(answer["created_at"]) == _moment(opened["created_at"])
        assert _moment(answer["closed_at"]) == _moment(ended["closed_at"])


def test_the_history_needs_a_login_token(client):
    for url in ("/encounters", "/encounters/any-id"):
        response = client.get(url)
        assert response.status_code == 401
        assert response.get_json()["error"] == "unauthorized"
