import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

AUTH_URL = os.environ.get("AUTH_URL", "https://localhost:5001").rstrip("/")
MONSTER_URL = os.environ.get("MONSTER_URL", "https://localhost:5002").rstrip("/")
ENCOUNTER_URL = os.environ.get("ENCOUNTER_URL", "https://encounter-service:5003").rstrip("/")
REQUEST_TIMEOUT = 3

def error(code, message, status=400):
    return jsonify(error=code, message=message), status

def require_json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body

def downstream_failure(response):
    try:
        return jsonify(response.json()), response.status_code
    except ValueError:
        return error("upstream_error", "An internal service request failed", 502)

def forward(method, url, **kwargs):
    try:
        res = requests.request(method, url, timeout=REQUEST_TIMEOUT, verify=False, **kwargs)
        if res.status_code >= 400:
            return None, downstream_failure(res)
        
        if res.content:
            data = res.json()
            if not isinstance(data, dict):
                raise ValueError("Internal service returned non-object JSON")
            return data, None
        return {}, None

    except requests.Timeout:
        return None, error("upstream_timeout", "An internal service did not respond in time", 504)
    except (requests.RequestException, ValueError):
        return None, error("upstream_error", "An internal service request failed", 502)

@app.post("/account")
def proxy_account():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/account", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 201

@app.post("/login")
def proxy_login():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/login", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/team")
def proxy_get_team():
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/team", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.put("/team")
def proxy_put_team():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("PUT", f"{ENCOUNTER_URL}/team", json=body, headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/challenges")
def proxy_get_challenges():
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/challenges", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.post("/encounters")
def proxy_post_encounters():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("POST", f"{ENCOUNTER_URL}/encounters", json=body, headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 201

@app.post("/encounters/<encounter_id>/action")
def proxy_post_encounter_action(encounter_id):
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("POST", f"{ENCOUNTER_URL}/encounters/{encounter_id}/action", json=body, headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/monsters")
def proxy_get_monsters():
    """Returns the complete catalog of the 16 monsters (US-10)."""
    data, failure = forward("GET", f"{MONSTER_URL}/monsters")
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/monsters/<int:monster_id>")
def proxy_get_monster_details(monster_id):
    """Returns the details of a specific monster (US-11)."""
    data, failure = forward("GET", f"{MONSTER_URL}/monsters/{monster_id}")
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/collection")
def proxy_get_collection():
    """Returns the player's collection and performs Lazy Init on the first access (US-06, US-09)."""
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{MONSTER_URL}/collection", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/internal/players/<string:player_id>/team")
def proxy_get_player_team(player_id):
    """Returns the player's team and owned species IDs (C9)."""
    headers = {}
    if "X-Internal-Secret" in request.headers:
        headers["X-Internal-Secret"] = request.headers["X-Internal-Secret"]

    data, failure = forward("GET", f"{MONSTER_URL}/internal/players/{player_id}/team", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.post("/internal/rewards")
def proxy_post_rewards():
    """Applies a stats or capture reward from the Encounter service (C10)."""
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    headers = {}
    if "X-Internal-Secret" in request.headers:
        headers["X-Internal-Secret"] = request.headers["X-Internal-Secret"]

    data, failure = forward("POST", f"{MONSTER_URL}/internal/rewards", json=body, headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 201

@app.get("/health")
def health():
    return jsonify(status="ok"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, ssl_context=("/certs/server.pem", "/certs/server.key"))