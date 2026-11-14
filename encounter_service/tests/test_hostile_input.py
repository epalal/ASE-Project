"""Hostile input (Lab 8): the service accepts only what it expects and answers 400
(or 413 for a body that is too big) to the rest, before doing any work."""

import pytest

SPROUTPAW, DRIFIN, EMBERBUN = 1, 5, 9  # catalogue IDs


def test_a_body_bigger_than_10_kb_is_refused_before_it_is_read(client, token_for):
    huge = '{"monster_ids": ["' + "a" * 11_000 + '"]}'

    response = client.put(
        "/team", data=huge, content_type="application/json", headers=token_for("player-1")
    )

    assert response.status_code == 413
    assert response.get_json()["error"] == "request_entity_too_large"


@pytest.mark.parametrize("hidden", ["\u0000", "\n", "\u001b[31m"])  # NUL, new line, terminal colour code
def test_a_monster_id_with_a_control_character_is_refused(client, token_for, monster_service, hidden):
    monster_service.give("player-1", "101", "105", "109")

    response = client.put(
        "/team", json={"monster_ids": ["101" + hidden, "105", "109"]}, headers=token_for("player-1")
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"


# The lab's list of valid-looking JSON that is not what we expect. The challenge ID
# must be a whole number that fits the database, so all of these are refused.
@pytest.mark.parametrize(
    "raw_body",
    [
        '{"challenge_id": NaN}',
        '{"challenge_id": Infinity}',
        '{"challenge_id": 1e999}',
        '{"challenge_id": 99999999999999999999}',
        '{"challenge_id": 1.5}',
        '{"challenge_id": true}',
        '{"challenge_id": "12"}',
        "not json at all",
    ],
)
def test_a_challenge_id_that_is_not_a_small_whole_number_is_refused(client, token_for, raw_body):
    response = client.post(
        "/encounters", data=raw_body, content_type="application/json", headers=token_for("player-1")
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"


@pytest.mark.parametrize("raw_body", ['{"action": "attack\\u0000"}', '{"action": NaN}', '{"action": ["attack"]}'])
def test_an_action_that_is_not_one_of_the_three_words_is_refused(game, client, token_for, raw_body):
    game.give_team("player-1", [SPROUTPAW, DRIFIN, EMBERBUN])
    encounter = game.open("player-1", SPROUTPAW).get_json()

    response = client.post(
        f"/encounters/{encounter['id']}/action",
        data=raw_body,
        content_type="application/json",
        headers=token_for("player-1"),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"


def test_a_monster_id_longer_than_64_characters_is_refused(client, token_for):
    response = client.put("/team", json={"monster_ids": ["a" * 65, "b", "c"]}, headers=token_for("player-1"))

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"
