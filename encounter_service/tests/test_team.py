"""Team endpoints (US-14, US-15, US-16), tested through the HTTP API."""

import pytest


def test_reading_the_team_needs_a_login_token(client):
    response = client.get("/team")

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


@pytest.fixture
def attacker_key():
    """A private key that is not the Player Service's."""
    return _other_private_key()


def _other_private_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def test_a_token_not_signed_by_the_player_service_is_refused(client, token_for, attacker_key):
    response = client.get("/team", headers=token_for("player-1", signing_key=attacker_key))

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_an_expired_token_is_refused(client, token_for):
    response = client.get("/team", headers=token_for("player-1", expires_in=-60))

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_a_token_without_an_expiry_is_refused(client, token_for):
    response = client.get("/team", headers=token_for("player-1", expires_in=None))

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_a_token_without_a_player_id_is_refused(client, token_for):
    response = client.get("/team", headers=token_for(None))

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_a_garbage_token_is_refused(client):
    response = client.get("/team", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_a_new_player_has_no_team_yet(client, token_for):
    response = client.get("/team", headers=token_for("player-1"))

    assert response.status_code == 200
    assert response.get_json() == {"monster_ids": []}


def test_a_player_can_save_a_team_of_three_monsters_they_own(client, token_for, monster_service):
    monster_service.give("player-1", "m1", "m2", "m3", "m4")

    saved = client.put("/team", json={"monster_ids": ["m1", "m2", "m4"]}, headers=token_for("player-1"))
    team = client.get("/team", headers=token_for("player-1"))

    assert saved.status_code == 200
    assert team.get_json() == {"monster_ids": ["m1", "m2", "m4"]}


def test_saving_again_replaces_the_team(client, token_for, monster_service):
    monster_service.give("player-1", "m1", "m2", "m3", "m4")
    client.put("/team", json={"monster_ids": ["m1", "m2", "m3"]}, headers=token_for("player-1"))

    client.put("/team", json={"monster_ids": ["m4", "m2", "m3"]}, headers=token_for("player-1"))
    team = client.get("/team", headers=token_for("player-1"))

    assert team.get_json() == {"monster_ids": ["m4", "m2", "m3"]}


def test_a_team_without_exactly_three_monsters_is_refused_and_the_old_team_is_kept(
    client, token_for, monster_service
):
    monster_service.give("player-1", "m1", "m2", "m3")
    client.put("/team", json={"monster_ids": ["m1", "m2", "m3"]}, headers=token_for("player-1"))

    refused = client.put("/team", json={"monster_ids": ["m1", "m2"]}, headers=token_for("player-1"))
    team = client.get("/team", headers=token_for("player-1"))

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "team_size"
    assert team.get_json() == {"monster_ids": ["m1", "m2", "m3"]}


def test_a_player_cannot_put_someone_elses_monster_in_their_team(client, token_for, monster_service):
    monster_service.give("player-1", "m1", "m2", "m3")
    monster_service.give("player-2", "x1", "x2", "x3")

    refused = client.put("/team", json={"monster_ids": ["m1", "m2", "x1"]}, headers=token_for("player-1"))

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "not_owned"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"monster_ids": "m1,m2,m3"},
        {"monster_ids": [1, 2, 3]},
        {"monster_ids": ["m1", "m2", "x" * 65]},
        ["m1", "m2", "m3"],
    ],
    ids=["no monster_ids", "not a list", "not text", "id too long", "list instead of object"],
)
def test_a_malformed_team_request_is_refused(client, token_for, monster_service, body):
    monster_service.give("player-1", "m1", "m2", "m3")

    refused = client.put("/team", json=body, headers=token_for("player-1"))

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "invalid_input"


def test_saving_a_team_while_the_monster_service_is_down_fails_cleanly(
    client, token_for, monster_service
):
    monster_service.give("player-1", "m1", "m2", "m3")
    client.put("/team", json={"monster_ids": ["m1", "m2", "m3"]}, headers=token_for("player-1"))
    monster_service.go_down()

    refused = client.put("/team", json={"monster_ids": ["m3", "m2", "m1"]}, headers=token_for("player-1"))
    team = client.get("/team", headers=token_for("player-1"))

    assert refused.status_code == 503
    assert refused.get_json()["error"] == "monster_service_unavailable"
    assert team.get_json() == {"monster_ids": ["m1", "m2", "m3"]}


def test_a_player_only_sees_their_own_team(client, token_for, monster_service):
    monster_service.give("player-1", "m1", "m2", "m3")
    client.put("/team", json={"monster_ids": ["m1", "m2", "m3"]}, headers=token_for("player-1"))

    other = client.get("/team", headers=token_for("player-2"))

    assert other.get_json() == {"monster_ids": []}


def test_a_team_request_that_is_not_json_is_refused(client, token_for):
    refused = client.put("/team", data="m1,m2,m3", headers=token_for("player-1"))

    assert refused.status_code == 400
    assert refused.get_json()["error"] == "invalid_input"
