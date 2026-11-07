"""Requests that arrive at the same moment (design rule 4: "a double click or a
retry cannot reward twice")."""

import threading

import pytest

SPROUTPAW, DRIFIN, EMBERBUN = 1, 5, 9
EXAMPLE_TEAM, EXAMPLE_WILD = [SPROUTPAW, DRIFIN, EMBERBUN], EMBERBUN  # P(win) about 57%


@pytest.fixture
def database_uri(tmp_path):
    """A real database file: each request gets its own connection, as with
    several server workers in production."""
    return f"sqlite:///{tmp_path / 'encounter.db'}"


def in_another_worker(request):
    """Run a request in its own thread, so it gets its own database session and
    connection, like a second server worker would."""
    result = {}
    worker = threading.Thread(target=lambda: result.setdefault("response", request()))
    worker.start()
    worker.join()
    return result["response"]


def test_a_second_click_while_the_first_is_being_rewarded_gets_nothing(game, dice, monster_service):
    game.give_team("player-1", EXAMPLE_TEAM)
    encounter = game.open("player-1", EXAMPLE_WILD).get_json()
    dice.next_roll = 0.10  # a win
    second = {}
    # The second click arrives while the first one is talking to the Monster Service.
    monster_service.while_rewarding = lambda: second.setdefault(
        "click", in_another_worker(lambda: game.act("player-1", encounter["id"], "attack"))
    )

    first = game.act("player-1", encounter["id"], "attack")

    assert first.get_json()["result"] == "win"
    assert second["click"].status_code == 409
    assert len(monster_service.rewards) == 1
