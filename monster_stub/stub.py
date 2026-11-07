"""Monster Service stub, for the Encounter Service's tests (built like Lab 6's history-stub).

It answers the calls the Encounter Service makes to the Monster Service with
canned data, in the same JSON format as Elena's real Monster Service:
  C9   GET  /internal/players/<player_id>/monsters  (needs the internal secret;
            same body as Elena's /collection)
  C3   GET  /monsters/<species_id>                   (Elena's catalogue entry)
  C10  POST /internal/rewards                       (needs the internal secret)

Like the Lab 6 stub, it records every call it receives (GET /__calls) and
forgets them (POST /__reset), so a test can check what the Encounter Service sent.

Special player IDs choose a failure, so a test can trigger it from outside:
  stub-500     the stub answers 500
  stub-slow    the stub answers only after STUB_SLOW_SECONDS (the caller should time out)
  stub-refuse  the stub refuses the reward with 409

The roll cannot be chosen from outside, so some players own monsters strong
enough to win against any challenge, even with the highest roll:
  stub-strong  its rewards are accepted
  stub-refuse  (above) its rewards are refused
"""

import os
import time

from flask import Flask, jsonify, request

# Elena's catalogue (initial_monsters.py): name, element, power (= base ATK), base HP.
ROSTER = {
    1: ("Sproutpaw", "Grass", 2, 2), 2: ("Vineclaw", "Grass", 4, 3),
    3: ("Bramblebane", "Grass", 5, 6), 4: ("Mossbear", "Grass", 3, 5),
    5: ("Drifin", "Water", 2, 3), 6: ("Tideglider", "Water", 4, 4),
    7: ("Dolwhale", "Water", 6, 7), 8: ("Frosthart", "Water", 5, 5),
    9: ("Emberbun", "Fire", 3, 2), 10: ("Blazetiger", "Fire", 5, 4),
    11: ("Cindrake", "Fire", 7, 6), 12: ("Ashwing", "Fire", 3, 2),
    13: ("Duskpaka", "Dark", 3, 5), 14: ("Colt", "Dark", 6, 3),
    15: ("Budbug", "Dark", 2, 3), 16: ("Leaflark", "Dark", 4, 3),
}  # fmt: skip
STARTERS = [1, 5, 9, 15]  # Elena's starter monsters: Sproutpaw, Drifin, Emberbun, Budbug
STRONG_PLAYERS = {"stub-strong", "stub-refuse"}
STRONG_STAT = 100  # three monsters at 100 beat any challenge with a win chance of exactly 1.0


def catalogue_entry(species_id):
    """A catalogue monster, as Elena's MonsterCatalog.to_dict() returns it."""
    name, element, power, hp = ROSTER[species_id]
    return {
        "id": species_id,
        "name": name,
        "element": element,
        "power": power,
        "hp": hp,
        "image_url": f"/assets/monsters/{name.lower()}.png",
    }


def owned_monster(player_id, species_id):
    """A player's monster, as Elena's PlayerMonster.to_dict() returns it. In the
    stub every starter has the ownership ID 100 + its species ID."""
    entry = catalogue_entry(species_id)
    strong = player_id in STRONG_PLAYERS
    return {
        "ownership_id": 100 + species_id,
        "player_id": player_id,
        "acquired_at": "2026-11-06T10:00:00+00:00",
        "atk": STRONG_STAT if strong else entry["power"],
        "hp": STRONG_STAT if strong else entry["hp"],
        "monster": entry,
    }


def create_stub(internal_secret=None, slow_seconds=None):
    app = Flask(__name__)
    secret = internal_secret or os.environ.get("INTERNAL_SERVICE_SECRET", "stub-secret")
    delay = slow_seconds if slow_seconds is not None else float(os.environ.get("STUB_SLOW_SECONDS", "5"))
    calls = []

    @app.before_request
    def record_the_call():
        if not request.path.startswith("/__") and request.path != "/health":
            # The address exactly as it was sent, still encoded (for example %2F).
            raw_path = (request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or request.path)
            calls.append(
                {"method": request.method, "path": raw_path.split("?")[0], "json": request.get_json(silent=True)}
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
        collection = [owned_monster(player_id, species_id) for species_id in STARTERS]
        return jsonify(player_id=player_id, count=len(collection), collection=collection)

    @app.get("/monsters/<int:species_id>")
    def species(species_id):
        if species_id not in ROSTER:
            return jsonify(error="Monster not found"), 404
        return jsonify(catalogue_entry(species_id))

    @app.post("/internal/rewards")
    def rewards():
        """Answers like Elena's C10: 200 for a stats reward, 201 for a capture."""
        body = request.get_json(silent=True) or {}
        failure = refused_secret() or chosen_failure(body.get("player_id"))
        if failure:
            return failure
        if body.get("player_id") == "stub-refuse":
            return jsonify(error="Player already owns this species"), 409
        if "owned_monster_ids" in body:
            return jsonify(message="Monster stats updated successfully", updated_monsters=[]), 200
        if "captured_species_id" in body:
            return jsonify(message="Monster reward granted successfully"), 201
        return jsonify(error="Specify either a stats reward or a capture reward"), 400

    return app


app = create_stub()  # what `flask --app stub run` and gunicorn load
