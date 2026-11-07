"""The Player Service stub signs login tokens the way the real Player Service will
(design rule 6), so the Bruno component tests can log in as any player."""

import jwt
import pytest

from app import create_app
from make_certs import make_certs
from player_stub import create_stub


@pytest.fixture
def tls(tmp_path):
    make_certs(tmp_path, services=["player-service", "encounter-service"])
    return tmp_path


@pytest.fixture
def player_stub(tls):
    return create_stub((tls / "player-service" / "jwt_private.pem").read_bytes()).test_client()


def test_a_token_from_the_player_stub_is_accepted_by_the_encounter_service(tls, player_stub, monster_service):
    tokens = player_stub.post("/__tokens", json={"player_ids": ["tamer-a"]}).get_json()["tokens"]
    encounter_service = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "JWT_PUBLIC_KEY": (tls / "encounter-service" / "jwt_public.pem").read_text(),
        },
        monster_client=monster_service,
    ).test_client()

    response = encounter_service.get("/team", headers={"Authorization": f"Bearer {tokens['tamer-a']}"})

    assert response.status_code == 200


def test_each_player_gets_a_token_in_their_own_name(tls, player_stub):
    tokens = player_stub.post("/__tokens", json={"player_ids": ["tamer-a", "tamer-b"]}).get_json()["tokens"]
    public_key = (tls / "encounter-service" / "jwt_public.pem").read_text()

    def owner(token):
        return jwt.decode(token, public_key, algorithms=["RS256"], audience="monster-tamers")["sub"]

    assert owner(tokens["tamer-a"]) == "tamer-a"
    assert owner(tokens["tamer-b"]) == "tamer-b"


@pytest.mark.parametrize("body", [None, {}, {"player_ids": "tamer-a"}, {"player_ids": []}, {"player_ids": [""]}])
def test_a_request_that_names_no_valid_players_gets_400(player_stub, body):
    response = player_stub.post("/__tokens", json=body)

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_input"
