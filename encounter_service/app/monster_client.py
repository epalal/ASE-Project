"""The port to Elena's Monster Service (seam S3).

The Encounter Service only ever talks to the Monster Service through this
interface. Production uses an HTTPS adapter (step 6); tests use an in-memory
fake. If the Monster Service renames a field, only the adapter changes.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OwnedMonster:
    """One of the player's monsters, as returned by C9."""

    id: str
    species_id: int
    name: str
    type: str
    atk: int
    hp: int


@dataclass(frozen=True)
class Species:
    """A catalogue monster with its base stats, as returned by C3."""

    id: int
    name: str
    type: str
    atk: int
    hp: int


class MonsterServiceUnavailable(Exception):
    """The Monster Service could not be reached or answered with an error."""


class MonsterServiceTimeout(MonsterServiceUnavailable):
    """The Monster Service did not answer in time."""


class RewardRefused(Exception):
    """The Monster Service answered and said no to a reward (for example, the
    player already owns the species). Retrying would not change the answer."""


class MonsterClient(Protocol):
    """Every call raises MonsterServiceUnavailable if the service cannot be reached.

    The two reward calls are C10, POST /internal/rewards. The Monster Service
    refuses a second reward for the same encounter ID, so retrying is safe."""

    def get_player_monsters(self, player_id: str) -> list[OwnedMonster]:
        """C9: GET /internal/players/{id}/monsters."""
        ...

    def get_species(self, species_id: int) -> Species:
        """C3: GET /monsters/{id}, the catalogue entry with base stats."""
        ...

    def grant_stats(
        self, encounter_id: str, player_id: str, owned_monster_ids: list[str], atk_bonus: int, hp_bonus: int
    ) -> None:
        """Reward for an attack win: raise these monsters' stats."""
        ...

    def grant_capture(self, encounter_id: str, player_id: str, species_id: int) -> None:
        """Reward for a capture: add this species to the player's collection."""
        ...
