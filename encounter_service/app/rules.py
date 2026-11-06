"""Game rules for encounters (docs/architecture.md, "Encounter rules").

Pure functions only: no Flask, no database, no randomness. The caller passes
the monsters' stats in and gets the numbers back, so every rule can be tested
on its own.
"""

import math
from dataclasses import dataclass
from typing import Callable, Collection, Sequence

# Each type beats exactly one other type; every other matchup is neutral.
BEATS = {"fire": "dark", "dark": "grass", "grass": "water", "water": "fire"}

TEAM_SIZE = 3
LOGISTIC_FACTOR = 0.6
CAPTURE_FACTOR = 0.75

# An attack win gives each team monster +1 ATK and +1 HP. The Monster Service
# owns the stats, so it applies the "base value + 3" limit.
WIN_ATK_BONUS = 1
WIN_HP_BONUS = 1


@dataclass(frozen=True)
class Monster:
    type: str
    atk: int
    hp: int


@dataclass(frozen=True)
class Chances:
    team_power: float
    challenge_power: float
    p_win: float
    p_capture: float | None  # None when capture is not offered


@dataclass(frozen=True)
class Outcome:
    result: str  # win, loss, captured, failed or escaped
    roll: float | None  # None for an escape, which never rolls


class UnknownAction(ValueError):
    """The action is not attack, capture or escape."""


class CaptureNotOffered(ValueError):
    """The player already owns the wild monster, so capture is not an option."""


class TeamRuleError(ValueError):
    """The chosen team breaks a team rule. `code` says which one."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def check_team(chosen_ids: Sequence[str], owned_ids: Collection[str]) -> None:
    """A team is exactly three different monsters owned by the player."""
    if len(chosen_ids) != TEAM_SIZE:
        raise TeamRuleError("team_size", f"A team must have exactly {TEAM_SIZE} monsters.")
    if len(set(chosen_ids)) != len(chosen_ids):
        raise TeamRuleError("duplicate_monster", "The same monster cannot fill two slots.")
    if any(monster_id not in owned_ids for monster_id in chosen_ids):
        raise TeamRuleError("not_owned", "A team can only use monsters you own.")


def _power(monster: Monster) -> float:
    return (monster.atk + monster.hp) / 2


def _type_modifier(attacker: str, defender: str) -> int:
    if BEATS[attacker] == defender:
        return 1
    if BEATS[defender] == attacker:
        return -1
    return 0


def compute_chances(team: Sequence[Monster], wild: Monster, wild_owned: bool) -> Chances:
    team_power = sum(
        max(0.0, _power(member) + _type_modifier(member.type, wild.type)) for member in team
    )
    challenge_power = 3 * _power(wild)
    p_win = 1 / (1 + math.exp(-LOGISTIC_FACTOR * (team_power - challenge_power)))
    p_capture = None if wild_owned else CAPTURE_FACTOR * p_win
    return Chances(
        team_power=team_power, challenge_power=challenge_power, p_win=p_win, p_capture=p_capture
    )


def resolve(action: str, chances: Chances, draw: Callable[[], float]) -> Outcome:
    """Resolve one action. `draw` returns a random number in [0, 1); it is only
    called when the action needs a roll, so an escape never rolls."""
    if action == "escape":
        return Outcome(result="escaped", roll=None)
    if action == "attack":
        roll = draw()
        return Outcome(result="win" if roll < chances.p_win else "loss", roll=roll)
    if action == "capture":
        if chances.p_capture is None:
            raise CaptureNotOffered()
        roll = draw()
        return Outcome(result="captured" if roll < chances.p_capture else "failed", roll=roll)
    raise UnknownAction(action)
