"""The real connection to the Monster Service (seam S3), tested over real HTTP
against the Monster Service stub, the way Lab 6 tests a service's dependency."""

import socket
import threading

import pytest
from werkzeug.serving import make_server

from app.http_monster_client import HttpMonsterClient
from app.monster_client import MonsterServiceUnavailable, OwnedMonster
from stub import create_stub

SECRET = "test-internal-secret"


@pytest.fixture
def stub_url():
    """Run the Monster Service stub on a free local port for one test."""
    stub = create_stub(internal_secret=SECRET, slow_seconds=1.0)
    server = make_server("127.0.0.1", 0, stub, threaded=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _port_with_nothing_listening():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_it_reads_a_players_monsters(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    monsters = monster_service.get_player_monsters("player-1")

    # The stub gives every player Elena's four starters with their base stats.
    assert monsters == [
        OwnedMonster(id="player-1-sproutpaw", species_id=1, name="Sproutpaw", type="grass", atk=2, hp=2),
        OwnedMonster(id="player-1-drifin", species_id=5, name="Drifin", type="water", atk=2, hp=3),
        OwnedMonster(id="player-1-emberbun", species_id=9, name="Emberbun", type="fire", atk=3, hp=2),
        OwnedMonster(id="player-1-budbug", species_id=15, name="Budbug", type="dark", atk=2, hp=3),
    ]


def test_an_unreachable_monster_service_is_reported_as_unavailable():
    monster_service = HttpMonsterClient(f"http://127.0.0.1:{_port_with_nothing_listening()}", internal_secret=SECRET)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("player-1")


def test_a_server_error_is_reported_as_unavailable(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("stub-500")  # the stub answers 500


def test_a_monster_service_that_is_too_slow_is_reported_as_unavailable(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET, timeout=0.2)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("stub-slow")  # the stub answers after 1 second
