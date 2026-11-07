"""The stubs' special players, which the Bruno component tests rely on.

In Docker the roll comes from the real secure generator, so a Bruno test cannot
choose it. Instead the Monster stub gives some players monsters so strong that
their attack wins even with the highest possible roll."""

import pytest

from app import create_app
from app.http_monster_client import HttpMonsterClient
from conftest import STUB_SECRET

HIGHEST_ROLL = 0.9999999999999999  # the largest number below 1
STARTER_TEAM = {"monster_ids": ["101", "105", "109"]}  # the stub's ownership IDs: 100 + species
CINDRAKE = 11  # the strongest wild monster


@pytest.fixture
def client_with_stub(stub_url, player_service_keys):
    _, public_pem = player_service_keys
    app = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_PUBLIC_KEY": public_pem},
        monster_client=HttpMonsterClient(stub_url, STUB_SECRET),
        draw=lambda: HIGHEST_ROLL,
    )
    return app.test_client()


def _attack(client, headers, challenge_id):
    client.put("/team", json=STARTER_TEAM, headers=headers)
    opened = client.post("/encounters", json={"challenge_id": challenge_id}, headers=headers).get_json()
    return client.post(f"/encounters/{opened['id']}/action", json={"action": "attack"}, headers=headers).get_json()


def test_the_strong_stub_player_wins_even_with_the_highest_roll(client_with_stub, token_for):
    result = _attack(client_with_stub, token_for("stub-strong"), CINDRAKE)

    assert result["p_win"] == 1.0
    assert result["result"] == "win"
    assert result["reward_status"] == "applied"


def test_the_refused_stub_player_always_wins_and_its_reward_is_refused(client_with_stub, token_for):
    result = _attack(client_with_stub, token_for("stub-refuse"), CINDRAKE)

    assert result["result"] == "win"
    assert result["reward_status"] == "failed"
