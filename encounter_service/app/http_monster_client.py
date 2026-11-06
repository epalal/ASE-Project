"""The real Monster Service adapter: the production side of seam S3.

It talks to the Monster Service over HTTPS and turns its JSON into the types
of the MonsterClient port, so the rest of the Encounter Service never sees HTTP
or the Monster Service's field names. Those names follow Elena's service:
a player's monster has a numeric `ownership_id`, and a catalogue entry has
`element` ("Grass") and `power` (its base ATK).
"""

from urllib.parse import quote

import requests

from .monster_client import MonsterServiceTimeout, MonsterServiceUnavailable, OwnedMonster, RewardRefused, Species

REQUEST_TIMEOUT = 3  # seconds, as in Lab 6: never wait forever for another service

# The Monster Service's "no" to a reward: invalid request (400), unknown monster or
# not the player's (404), already owns the species or conflict (409). Asking again
# gets the same answer. Any other error (5xx, or 403 from a wrong internal secret)
# is our problem or the network's, so the reward stays pending and is retried.
REFUSAL_CODES = {400, 404, 409}


class HttpMonsterClient:
    def __init__(self, base_url, internal_secret, timeout=REQUEST_TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["X-Internal-Secret"] = internal_secret

    def get_player_monsters(self, player_id):
        """C9: same body as the Monster Service's /collection, for any player."""
        body = self._get(f"/internal/players/{quote(player_id, safe='')}/monsters")
        return [
            OwnedMonster(
                id=str(owned["ownership_id"]),
                species_id=owned["monster"]["id"],
                name=owned["monster"]["name"],
                type=owned["monster"]["element"].lower(),
                atk=owned["atk"],
                hp=owned["hp"],
            )
            for owned in body["collection"]
        ]

    def get_species(self, species_id):
        """C3: the public catalogue entry, with the species' base stats."""
        entry = self._get(f"/monsters/{int(species_id)}")
        return Species(
            id=entry["id"], name=entry["name"], type=entry["element"].lower(), atk=entry["power"], hp=entry["hp"]
        )

    def grant_stats(self, encounter_id, player_id, owned_monster_ids, atk_bonus, hp_bonus):
        """C10, stats reward. The Monster Service's ownership IDs are numbers."""
        self._post_reward(
            {
                "player_id": player_id,
                "encounter_id": encounter_id,
                "owned_monster_ids": [int(monster_id) for monster_id in owned_monster_ids],
                "atk_bonus": atk_bonus,
                "hp_bonus": hp_bonus,
            }
        )

    def grant_capture(self, encounter_id, player_id, species_id):
        """C10, capture reward: add this species to the player's collection."""
        self._post_reward(
            {"player_id": player_id, "encounter_id": encounter_id, "captured_species_id": int(species_id)}
        )

    def _post_reward(self, body):
        try:
            response = self._session.post(f"{self._base_url}/internal/rewards", json=body, timeout=self._timeout)
        except requests.Timeout as failure:
            raise MonsterServiceTimeout() from failure
        except requests.RequestException as failure:
            raise MonsterServiceUnavailable() from failure
        if response.status_code in REFUSAL_CODES:
            raise RewardRefused()
        if not response.ok:
            raise MonsterServiceUnavailable()

    def _get(self, path):
        try:
            response = self._session.get(self._base_url + path, timeout=self._timeout)
            response.raise_for_status()  # an error answer is not data
        except requests.Timeout as failure:
            raise MonsterServiceTimeout() from failure
        except requests.RequestException as failure:
            raise MonsterServiceUnavailable() from failure
        return response.json()
