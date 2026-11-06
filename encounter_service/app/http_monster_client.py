"""The real Monster Service adapter: the production side of seam S3.

It talks to the Monster Service over HTTPS and turns its JSON into the types
of the MonsterClient port, so the rest of the Encounter Service never sees HTTP.
"""

from urllib.parse import quote

import requests

from .monster_client import MonsterServiceUnavailable, OwnedMonster


REQUEST_TIMEOUT = 3  # seconds, as in Lab 6: never wait forever for another service


class HttpMonsterClient:
    def __init__(self, base_url, internal_secret, timeout=REQUEST_TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["X-Internal-Secret"] = internal_secret

    def get_player_monsters(self, player_id):
        body = self._get(f"/internal/players/{quote(player_id, safe='')}/monsters")
        return [
            OwnedMonster(
                id=m["id"], species_id=m["species_id"], name=m["name"], type=m["type"], atk=m["atk"], hp=m["hp"]
            )
            for m in body["monsters"]
        ]

    def _get(self, path):
        try:
            response = self._session.get(self._base_url + path, timeout=self._timeout)
            response.raise_for_status()  # an error answer is not data
        except requests.RequestException as failure:
            raise MonsterServiceUnavailable() from failure
        return response.json()
