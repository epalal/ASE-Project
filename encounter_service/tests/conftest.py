import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app
from app.monster_client import MonsterServiceUnavailable, OwnedMonster


class FakeMonsterService:
    """Stands in for Elena's Monster Service at the network boundary (C9)."""

    def __init__(self):
        self._owned = {}
        self._down = False

    def go_down(self):
        self._down = True

    def give(self, player_id, *monster_ids):
        self._owned.setdefault(player_id, []).extend(
            OwnedMonster(id=monster_id, species_id=1, name="Sproutpaw", type="grass", atk=2, hp=2)
            for monster_id in monster_ids
        )

    def get_player_monsters(self, player_id):
        if self._down:
            raise MonsterServiceUnavailable()
        return list(self._owned.get(player_id, []))


@pytest.fixture
def monster_service():
    return FakeMonsterService()


def _key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem.decode()


@pytest.fixture(scope="session")
def player_service_keys():
    """Stands in for the Player Service's key pair: it signs, we only verify."""
    return _key_pair()


@pytest.fixture
def token_for(player_service_keys):
    """Authorization header for a player, signed like the Player Service will sign it."""
    private_pem, _ = player_service_keys

    def make(player_id, signing_key=private_pem, expires_in=900):
        now = dt.datetime.now(dt.timezone.utc)
        claims = {"iat": now}
        if player_id is not None:
            claims["sub"] = player_id
        if expires_in is not None:
            claims["exp"] = now + dt.timedelta(seconds=expires_in)
        token = jwt.encode(claims, signing_key, algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def app(player_service_keys, monster_service):
    _, public_pem = player_service_keys
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "JWT_PUBLIC_KEY": public_pem,
        },
        monster_client=monster_service,
    )


@pytest.fixture
def client(app):
    return app.test_client()
