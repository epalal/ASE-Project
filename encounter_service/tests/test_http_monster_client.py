"""The real connection to the Monster Service (seam S3), tested over real HTTP
against the Monster Service stub, the way Lab 6 tests a service's dependency."""

import socket
import threading

import pytest
import requests
from werkzeug.serving import make_server

from app.http_monster_client import HttpMonsterClient
from app.monster_client import (
    MonsterServiceTimeout,
    MonsterServiceUnavailable,
    OwnedMonster,
    RewardRefused,
    Species,
)
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

    # The stub gives every player Elena's four starters with their base stats, in
    # her format (numeric ownership_id, element "Grass"). The adapter turns them into
    # the port's types: IDs as text, types in lower case.
    assert monsters == [
        OwnedMonster(id="101", species_id=1, name="Sproutpaw", type="grass", atk=2, hp=2),
        OwnedMonster(id="105", species_id=5, name="Drifin", type="water", atk=2, hp=3),
        OwnedMonster(id="109", species_id=9, name="Emberbun", type="fire", atk=3, hp=2),
        OwnedMonster(id="115", species_id=15, name="Budbug", type="dark", atk=2, hp=3),
    ]


def test_it_reads_a_wild_monsters_base_stats_from_the_catalogue(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    # Elena's catalogue says element "Fire" and power 3 (the roster slide's ATK).
    assert monster_service.get_species(9) == Species(id=9, name="Emberbun", type="fire", atk=3, hp=2)


def last_call_received(stub_url):
    """What the stub received last, read from its /__calls like in Lab 6."""
    return requests.get(f"{stub_url}/__calls", timeout=3).json()[-1]


def test_a_stats_reward_is_sent_in_the_monster_services_format(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    monster_service.grant_stats("encounter-1", "player-1", ["101", "105", "109"], atk_bonus=1, hp_bonus=1)

    assert last_call_received(stub_url) == {
        "method": "POST",
        "path": "/internal/rewards",
        "json": {
            "player_id": "player-1",
            "encounter_id": "encounter-1",
            "owned_monster_ids": [101, 105, 109],  # Elena's ownership IDs are numbers
            "atk_bonus": 1,
            "hp_bonus": 1,
        },
    }


def test_a_capture_reward_is_sent_in_the_monster_services_format(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    monster_service.grant_capture("encounter-2", "player-1", 1)

    assert last_call_received(stub_url) == {
        "method": "POST",
        "path": "/internal/rewards",
        "json": {"player_id": "player-1", "encounter_id": "encounter-2", "captured_species_id": 1},
    }


def test_a_reward_the_monster_service_says_no_to_is_reported_as_refused(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    with pytest.raises(RewardRefused):
        monster_service.grant_capture("encounter-3", "stub-refuse", 1)  # the stub answers 409


def test_a_wrong_internal_secret_is_reported_as_unavailable_not_refused(stub_url):
    # A configuration mistake on our side must not fail rewards for good:
    # it stays pending and is retried once the secret is fixed.
    monster_service = HttpMonsterClient(stub_url, internal_secret="not-the-secret")

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.grant_stats("encounter-4", "player-1", ["101"], atk_bonus=1, hp_bonus=1)


def test_a_player_id_cannot_change_which_address_is_called(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("../../internal/rewards")

    assert last_call_received(stub_url)["path"] == "/internal/players/..%2F..%2Finternal%2Frewards/monsters"


def test_an_unreachable_monster_service_is_reported_as_unavailable():
    monster_service = HttpMonsterClient(f"http://127.0.0.1:{_port_with_nothing_listening()}", internal_secret=SECRET)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("player-1")


def test_a_server_error_is_reported_as_unavailable(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET)

    with pytest.raises(MonsterServiceUnavailable):
        monster_service.get_player_monsters("stub-500")  # the stub answers 500


def test_a_monster_service_that_is_too_slow_is_reported_as_a_timeout(stub_url):
    monster_service = HttpMonsterClient(stub_url, internal_secret=SECRET, timeout=0.2)

    with pytest.raises(MonsterServiceTimeout):
        monster_service.get_player_monsters("stub-slow")  # the stub answers after 1 second
