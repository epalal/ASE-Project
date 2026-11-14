import datetime as dt
import threading

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from werkzeug.serving import make_server

from app import create_app
from stub import create_stub

STUB_SECRET = "test-internal-secret"


def run_in_background(wsgi_app, ssl_context=None):
    """Serve a WSGI app on a free local port; returns the server (stop it with shutdown())."""
    server = make_server("127.0.0.1", 0, wsgi_app, threaded=True, ssl_context=ssl_context)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return server


@pytest.fixture
def stub_url():
    """The Monster Service stub, over real HTTP on a free local port, for one test."""
    server = run_in_background(create_stub(internal_secret=STUB_SECRET, slow_seconds=1.0))
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
from app.monster_client import (
    MonsterServiceTimeout,
    MonsterServiceUnavailable,
    OwnedMonster,
    RewardRefused,
    Species,
)

# The roster slide: catalogue ID, name, type, base ATK, base HP.
ROSTER = [
    Species(1, "Sproutpaw", "grass", 2, 2), Species(2, "Vineclaw", "grass", 4, 3),
    Species(3, "Bramblebane", "grass", 5, 6), Species(4, "Mossbear", "grass", 3, 5),
    Species(5, "Drifin", "water", 2, 3), Species(6, "Tideglider", "water", 4, 4),
    Species(7, "Dolwhale", "water", 6, 7), Species(8, "Frosthart", "water", 5, 5),
    Species(9, "Emberbun", "fire", 3, 2), Species(10, "Blazetiger", "fire", 5, 4),
    Species(11, "Cindrake", "fire", 7, 6), Species(12, "Ashwing", "fire", 3, 2),
    Species(13, "Duskpaka", "dark", 3, 5), Species(14, "Colt", "dark", 6, 3),
    Species(15, "Budbug", "dark", 2, 3), Species(16, "Leaflark", "dark", 4, 3),
]  # fmt: skip


class FakeMonsterService:
    """Stands in for Elena's Monster Service at the network boundary
    (C9 for a player's monsters, C3 for the catalogue)."""

    def __init__(self):
        self._catalogue = {species.id: species for species in ROSTER}
        self._owned = {}
        self._down = False
        self._slow = False
        self._refusing = False
        self.rewards = []  # what C10 received, like the Lab 6 stub's /__calls
        self.refused_rewards = []  # rewards it said no to
        self.while_rewarding = None  # runs once, in the middle of a reward call

    def refuse_rewards(self):
        """Answer every reward with a refusal, as the real service does for example
        when the player already owns the species."""
        self._refusing = True

    def _answer(self):
        """Fail the way the real service would if it were down or too slow."""
        if self._slow:
            raise MonsterServiceTimeout()
        if self._down:
            raise MonsterServiceUnavailable()

    def _reward_received(self, reward):
        self._answer()
        if self._refusing:
            self.refused_rewards.append(reward)
            raise RewardRefused()
        interruption, self.while_rewarding = self.while_rewarding, None
        if interruption:
            interruption()
        self.rewards.append(reward)

    def go_down(self):
        self._down = True

    def go_slow(self):
        self._slow = True

    def come_back(self):
        self._down = self._slow = False

    def give(self, player_id, *monster_ids, species_id=1):
        """Give the player monsters of one species, with that species' base stats."""
        species = self._catalogue[species_id]
        self._owned.setdefault(player_id, []).extend(
            OwnedMonster(
                id=monster_id,
                species_id=species.id,
                name=species.name,
                type=species.type,
                atk=species.atk,
                hp=species.hp,
            )
            for monster_id in monster_ids
        )

    def forget(self, player_id, monster_id):
        """The Monster Service no longer has this monster (for example after a reset)."""
        self._owned[player_id] = [m for m in self._owned.get(player_id, []) if m.id != monster_id]

    def get_player_monsters(self, player_id):
        self._answer()
        return list(self._owned.get(player_id, []))

    def get_species(self, species_id):
        self._answer()
        return self._catalogue[species_id]

    def grant_stats(self, encounter_id, player_id, owned_monster_ids, atk_bonus, hp_bonus):
        self._reward_received(
            {
                "kind": "stats",
                "encounter_id": encounter_id,
                "player_id": player_id,
                "owned_monster_ids": list(owned_monster_ids),
                "atk_bonus": atk_bonus,
                "hp_bonus": hp_bonus,
            }
        )

    def grant_capture(self, encounter_id, player_id, species_id):
        self._reward_received(
            {"kind": "capture", "encounter_id": encounter_id, "player_id": player_id, "species_id": species_id}
        )


@pytest.fixture
def monster_service():
    return FakeMonsterService()


class Dice:
    """Stands in for the secure random generator: the test decides the roll."""

    def __init__(self):
        self.next_roll = 0.5

    def roll(self):
        return self.next_roll


@pytest.fixture
def dice():
    return Dice()


class Game:
    """Small helpers so the tests read like the game."""

    def __init__(self, client, token_for, monster_service):
        self._client = client
        self._token_for = token_for
        self._monster_service = monster_service

    def give_team(self, player_id, species_ids):
        """Give the player one monster of each species, save them as the team,
        and return their IDs in slot order."""
        monster_ids = []
        for species_id in species_ids:
            monster_id = f"{player_id}-monster-{species_id}"
            self._monster_service.give(player_id, monster_id, species_id=species_id)
            monster_ids.append(monster_id)
        self._client.put("/team", json={"monster_ids": monster_ids}, headers=self._token_for(player_id))
        return monster_ids

    def open(self, player_id, challenge_id):
        return self._client.post(
            "/encounters", json={"challenge_id": challenge_id}, headers=self._token_for(player_id)
        )

    def act(self, player_id, encounter_id, action):
        return self._client.post(
            f"/encounters/{encounter_id}/action", json={"action": action}, headers=self._token_for(player_id)
        )

    def history(self, player_id):
        return self._client.get("/encounters", headers=self._token_for(player_id))

    def show(self, player_id, encounter_id):
        return self._client.get(f"/encounters/{encounter_id}", headers=self._token_for(player_id))


@pytest.fixture
def game(client, token_for, monster_service):
    return Game(client, token_for, monster_service)


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


@pytest.fixture(scope="session")
def attacker_key():
    """A private key that is not the Player Service's."""
    private_pem, _ = _key_pair()
    return private_pem


@pytest.fixture
def token_for(player_service_keys):
    """Authorization header for a player, signed like the Player Service will sign it."""
    private_pem, _ = player_service_keys

    def make(
        player_id,
        signing_key=private_pem,
        expires_in=900,
        audience="monster-tamers",
        issuer="player-service",
    ):
        """A None argument leaves that claim out of the token."""
        now = dt.datetime.now(dt.timezone.utc)
        claims = {"iat": now}
        if player_id is not None:
            claims["sub"] = player_id
        if expires_in is not None:
            claims["exp"] = now + dt.timedelta(seconds=expires_in)
        if audience is not None:
            claims["aud"] = audience
        if issuer is not None:
            claims["iss"] = issuer
        token = jwt.encode(claims, signing_key, algorithm="RS256")
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def database_uri():
    """An in-memory database by default; a test module can override this."""
    return "sqlite://"


@pytest.fixture
def app(player_service_keys, monster_service, dice, database_uri):
    _, public_pem = player_service_keys
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "JWT_PUBLIC_KEY": public_pem,
            "DATA_KEY": Fernet.generate_key(),
        },
        monster_client=monster_service,
        draw=dice.roll,
    )


@pytest.fixture
def client(app):
    return app.test_client()
