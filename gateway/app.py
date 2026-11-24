import os
import requests
from flask import Blueprint, Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

gateway_bp = Blueprint("gateway", __name__)
limiter = Limiter(key_func=get_remote_address, default_limits=[])

AUTH_URL = os.environ.get("AUTH_URL", "https://localhost:5001").rstrip("/")
MONSTER_URL = os.environ.get("MONSTER_URL", "https://localhost:5002").rstrip("/")
ENCOUNTER_URL = os.environ.get("ENCOUNTER_URL", "https://encounter-service:5003").rstrip("/")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:8080")
REQUEST_TIMEOUT = 3

CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "/certs/ca.pem")

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
        res = requests.request(method, url, timeout=REQUEST_TIMEOUT, verify=CA_CERT_PATH, **kwargs)
        if res.status_code >= 400:
            return None, downstream_failure(res)
        
        if res.content:
            data = res.json()
            return data, None
        return {}, None

    except requests.Timeout:
        return None, error("upstream_timeout", "An internal service did not respond in time", 504)
    except (requests.RequestException, ValueError):
        return None, error("upstream_error", "An internal service request failed", 502)

@gateway_bp.post("/account")
def proxy_account():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/account", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 201

@gateway_bp.post("/login")
def proxy_login():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/login", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/team")
def proxy_get_team():
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/team", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.put("/team")
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

@gateway_bp.get("/challenges")
def proxy_get_challenges():
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/challenges", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/encounters")
def proxy_get_history():
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/encounters", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/encounters/<encounter_id>")
def proxy_get_encounter(encounter_id):
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{ENCOUNTER_URL}/encounters/{encounter_id}", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.post("/encounters")
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

@gateway_bp.post("/encounters/<encounter_id>/action")
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

@gateway_bp.get("/monsters")
@limiter.limit("30 per minute")
def proxy_get_monsters():
    """Returns the complete catalog of the 16 monsters (US-10)."""
    data, failure = forward("GET", f"{MONSTER_URL}/monsters")
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/monsters/<int:monster_id>")
def proxy_get_monster_details(monster_id):
    """Returns the details of a specific monster (US-11)."""
    data, failure = forward("GET", f"{MONSTER_URL}/monsters/{monster_id}")
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/collection")
@limiter.limit("30 per minute")
def proxy_get_collection():
    """Returns the player's collection and performs Lazy Init on the first access (US-06, US-09)."""
    headers = {}
    if "Authorization" in request.headers:
        headers["Authorization"] = request.headers["Authorization"]

    data, failure = forward("GET", f"{MONSTER_URL}/collection", headers=headers)
    if failure is not None:
        return failure
    return jsonify(data), 200

@gateway_bp.get("/health")
def health():
    return jsonify(status="ok"), 200


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        RATELIMIT_STORAGE_URI=os.environ.get(
            "RATELIMIT_STORAGE_URI",
            "redis://rate-limit-store:6379/0",
        ),
        RATELIMIT_HEADERS_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)

    limiter.init_app(app)
    app.register_blueprint(gateway_bp)

    @app.after_request
    def allow_the_frontend(response):
        response.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
        return response

    @app.errorhandler(429)
    def handle_rate_limit_exceeded(_error):
        return jsonify(error="rate_limit_exceeded", message="Too many requests"), 429

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, ssl_context=("/certs/server.pem", "/certs/server.key"))