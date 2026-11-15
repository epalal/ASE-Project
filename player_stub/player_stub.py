"""Player Service stub, for the Encounter Service's component tests (built like Lab 6's history-stub).

The Encounter Service never calls the Player Service: it only checks the login
tokens the Player Service signs. This stub signs them the same way (design rule 6),
with the key that tls-init makes for the Player Service, so a Bruno test can log
in as any player, including the Monster stub's special players.

  POST /__tokens  {"player_ids": ["tamer-a", ...]}  ->  {"tokens": {"tamer-a": "<token>", ...}}
  GET  /health

Each token lasts 15 minutes and carries exp, sub, aud and iss, like a real one.
"""

import datetime as dt
import os

import jwt
from flask import Flask, jsonify, request

TOKEN_LIFETIME = dt.timedelta(minutes=15)
MAX_PLAYERS = 20
MAX_ID_LENGTH = 64


def _player_ids_from(body):
    """Accept only {"player_ids": [1 to 20 non-empty texts]}; anything else is None."""
    if not isinstance(body, dict):
        return None
    player_ids = body.get("player_ids")
    if not isinstance(player_ids, list) or not 0 < len(player_ids) <= MAX_PLAYERS:
        return None
    if not all(isinstance(i, str) and 0 < len(i) <= MAX_ID_LENGTH for i in player_ids):
        return None
    return player_ids


def create_stub(private_key=None):
    """Without a key, it reads the one tls-init put in this service's volume."""
    if private_key is None:
        with open(os.environ.get("JWT_PRIVATE_KEY_PATH", "/certs/jwt_private.pem"), "rb") as key_file:
            private_key = key_file.read()
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="player_stub")

    @app.post("/__tokens")
    def tokens():
        player_ids = _player_ids_from(request.get_json(silent=True))
        if player_ids is None:
            return jsonify(error="invalid_input", message='Send {"player_ids": ["<player ID>", ...]}.'), 400
        now = dt.datetime.now(dt.timezone.utc)
        return jsonify(
            tokens={
                player_id: jwt.encode(
                    {
                        "sub": player_id,
                        "iat": now,
                        "exp": now + TOKEN_LIFETIME,
                        "aud": "monster-tamers",
                        "iss": "player-service",
                    },
                    private_key,
                    algorithm="RS256",
                )
                for player_id in player_ids
            }
        )

    return app
