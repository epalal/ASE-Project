"""Game rules (docs/architecture.md, "Encounter rules")."""

import pytest

from app.rules import (
    CaptureNotOffered,
    Chances,
    Monster,
    TeamRuleError,
    UnknownAction,
    check_team,
    compute_chances,
    resolve,
)

SPROUTPAW = Monster("grass", atk=2, hp=2)
DRIFIN = Monster("water", atk=2, hp=3)
EMBERBUN = Monster("fire", atk=3, hp=2)


def test_worked_example_from_the_design_doc():
    # Doc example: Sproutpaw 2 + Drifin 3.5 (Water beats Fire, +1) + Emberbun 2.5
    # against a wild Emberbun: team power 8, challenge power 7.5, P(win) about 57%.
    chances = compute_chances([SPROUTPAW, DRIFIN, EMBERBUN], wild=EMBERBUN, wild_owned=True)

    assert chances.team_power == 8
    assert chances.challenge_power == 7.5
    assert chances.p_win == pytest.approx(0.57, abs=0.005)


# Slide 3: "Equal power -> 50%, 5-point advantage -> about 95%, 5-point disadvantage -> about 5%".
# Dark against Water is neutral, so these teams get no type bonus.
@pytest.mark.parametrize(
    "team, wild, expected",
    [
        ([Monster("dark", 2, 2)] * 3, Monster("water", 2, 2), 0.50),  # 6 vs 6
        (
            [Monster("dark", 4, 4), Monster("dark", 4, 3), Monster("dark", 3, 4)],
            Monster("water", 2, 2),
            0.95,
        ),  # 11 vs 6
        (
            [Monster("dark", 1, 1), Monster("dark", 1, 2), Monster("dark", 2, 1)],
            Monster("water", 3, 3),
            0.05,
        ),  # 4 vs 9
    ],
    ids=["equal power", "five points stronger", "five points weaker"],
)
def test_win_chance_matches_the_slide_anchor_points(team, wild, expected):
    assert compute_chances(team, wild, wild_owned=True).p_win == pytest.approx(expected, abs=0.005)


def test_capture_chance_is_three_quarters_of_the_win_chance():
    # Doc example: P(win) about 57%, so P(capture) about 43%.
    chances = compute_chances([SPROUTPAW, DRIFIN, EMBERBUN], wild=EMBERBUN, wild_owned=False)

    assert chances.p_capture == pytest.approx(0.43, abs=0.005)


def test_capture_is_not_offered_for_a_monster_the_player_already_owns():
    chances = compute_chances([SPROUTPAW, DRIFIN, EMBERBUN], wild=EMBERBUN, wild_owned=True)

    assert chances.p_capture is None


# Resolving an action. P(win) 50% and P(capture) 37.5% keep the boundaries easy to read.
EVEN = Chances(team_power=6, challenge_power=6, p_win=0.5, p_capture=0.375)


def always(value):
    return lambda: value


def test_attack_wins_when_the_roll_is_lower_than_the_win_chance():
    outcome = resolve("attack", EVEN, draw=always(0.49))

    assert outcome.result == "win"
    assert outcome.roll == 0.49


def test_attack_loses_when_the_roll_equals_or_exceeds_the_win_chance():
    assert resolve("attack", EVEN, draw=always(0.5)).result == "loss"
    assert resolve("attack", EVEN, draw=always(0.9)).result == "loss"


def test_capture_succeeds_when_the_roll_is_lower_than_the_capture_chance():
    assert resolve("capture", EVEN, draw=always(0.37)).result == "captured"


def test_capture_fails_when_the_roll_equals_or_exceeds_the_capture_chance():
    # 0.4 would win an attack, but it is above the 37.5% capture chance.
    assert resolve("capture", EVEN, draw=always(0.4)).result == "failed"


def test_capture_is_refused_when_it_is_not_offered():
    owned = Chances(team_power=6, challenge_power=6, p_win=0.5, p_capture=None)

    with pytest.raises(CaptureNotOffered):
        resolve("capture", owned, draw=always(0.1))


def test_escape_always_works_and_never_rolls():
    def no_roll():
        raise AssertionError("escape must not roll")

    outcome = resolve("escape", EVEN, draw=no_roll)

    assert outcome.result == "escaped"
    assert outcome.roll is None


def test_an_unknown_action_is_refused():
    with pytest.raises(UnknownAction):
        resolve("dance", EVEN, draw=always(0.1))


# Team rules (US-14, US-15, US-16): exactly three different monsters the player owns.
OWNED = {"m1", "m2", "m3", "m4"}


def test_three_different_owned_monsters_make_a_valid_team():
    check_team(["m1", "m2", "m4"], owned_ids=OWNED)  # no error


@pytest.mark.parametrize("chosen", [["m1", "m2"], ["m1", "m2", "m3", "m4"], []])
def test_a_team_must_have_exactly_three_monsters(chosen):
    with pytest.raises(TeamRuleError) as error:
        check_team(chosen, owned_ids=OWNED)

    assert error.value.code == "team_size"


def test_the_same_monster_cannot_fill_two_slots():
    with pytest.raises(TeamRuleError) as error:
        check_team(["m1", "m1", "m2"], owned_ids=OWNED)

    assert error.value.code == "duplicate_monster"


def test_a_team_can_only_use_monsters_the_player_owns():
    with pytest.raises(TeamRuleError) as error:
        check_team(["m1", "m2", "someone_elses"], owned_ids=OWNED)

    assert error.value.code == "not_owned"
