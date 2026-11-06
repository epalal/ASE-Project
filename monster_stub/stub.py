"""Monster Service stub, for the Encounter Service's tests (built like Lab 6's history-stub).

It answers the calls the Encounter Service makes to the Monster Service with
canned data:
  C9   GET  /internal/players/<player_id>/monsters  (needs the internal secret)
  C3   GET  /monsters/<species_id>
  C10  POST /internal/rewards                       (needs the internal secret)

Like the Lab 6 stub, it records every call it receives (GET /__calls) and
forgets them (POST /__reset), so a test can check what the Encounter Service sent.

Special player IDs choose a failure, so a test can trigger it from outside:
  stub-500     the stub answers 500
  stub-slow    the stub answers only after STUB_SLOW_SECONDS (the caller should time out)
  stub-refuse  the stub refuses the reward with 409
"""

import os
import time

from flask import Flask, jsonify, request

# The roster slide with the IDs of Elena's catalogue: name, type, base ATK, base HP.
ROSTER = {
    1: ("Sproutpaw", "grass", 2, 2), 2: ("Vineclaw", "grass", 4, 3),
    3: ("Bramblebane", "grass", 5, 6), 4: ("Mossbear", "grass", 3, 5),
    5: ("Drifin", "water", 2, 3), 6: ("Tideglider", "water", 4, 4),
    7: ("Dolwhale", "water", 6, 7), 8: ("Frosthart", "water", 5, 5),
    9: ("Emberbun", "fire", 3, 2), 10: ("Blazetiger", "fire", 5, 4),
    11: ("Cindrake", "fire", 7, 6), 12: ("Ashwing", "fire", 3, 2),
    13: ("Duskpaka", "dark", 3, 5), 14: ("Colt", "dark", 6, 3),
    15: ("Budbug", "dark", 2, 3), 16: ("Leaflark", "dark", 4, 3),
}  # fmt: skip
STARTERS = [1, 5, 9, 15]  # Elena's starter monsters: Sproutpaw, Drifin, Emberbun, Budbug


def create_stub(internal_secret=None, slow_seconds=None):
    app = Flask(__name__)
    secret = internal_secret or os.environ.get("INTERNAL_SERVICE_SECRET", "stub-secret")
    delay = slow_seconds if slow_seconds is not None else float(os.environ.get("STUB_SLOW_SECONDS", "5"))
    calls = []

    @app.before_request
    def record_the_call():
        if not request.path.startswith("/__") and request.path != "/health":
            calls.append(
                {"method": request.method, "path": request.path, "json": request.get_json(silent=True)}
            )

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="monster_stub")

    @app.get("/__calls")
    def received_calls():
        return jsonify(calls)

    @app.post("/__reset")
    def reset():
        calls.clear()
        return "", 204

    def refused_secret():
        if request.headers.get("X-Internal-Secret") != secret:
            return jsonify(error="forbidden", message="Wrong internal secret."), 403
        return None

    def chosen_failure(player_id):
        if player_id == "stub-500":
            return jsonify(error="stub_failure", message="The stub was asked to fail."), 500
        if player_id == "stub-slow":
            time.sleep(delay)
        return None

    @app.get("/internal/players/<player_id>/monsters")
    def player_monsters(player_id):
        failure = refused_secret() or chosen_failure(player_id)
        if failure:
            return failure
        monsters = []
        for species_id in STARTERS:
            name, monster_type, atk, hp = ROSTER[species_id]
            monsters.append(
                {
                    "id": f"{player_id}-{name.lower()}",
                    "species_id": species_id,
                    "name": name,
                    "type": monster_type,
                    "atk": atk,
                    "hp": hp,
                }
            )
        return jsonify(monsters=monsters)

    @app.get("/monsters/<int:species_id>")
    def species(species_id):
        if species_id not in ROSTER:
            return jsonify(error="not_found", message="No such monster."), 404
        name, monster_type, atk, hp = ROSTER[species_id]
        return jsonify(
            id=species_id,
            name=name,
            type=monster_type,
            atk=atk,
            hp=hp,
            image_url=f"/assets/monsters/{name.lower()}.png",
        )

    @app.post("/internal/rewards")
    def rewards():
        body = request.get_json(silent=True) or {}
        failure = refused_secret() or chosen_failure(body.get("player_id"))
        if failure:
            return failure
        if body.get("player_id") == "stub-refuse":
            return jsonify(error="reward_refused", message="The stub refuses this reward."), 409
        return jsonify(encounter_id=body.get("encounter_id"), applied=True), 201

    return app


app = create_stub()  # what `flask --app stub run` and gunicorn load
