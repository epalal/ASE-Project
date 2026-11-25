from datetime import datetime, timezone
import json
import logging
import os
from urllib.parse import quote

from flask import Blueprint, Flask, Response, current_app, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
from werkzeug.exceptions import HTTPException

gateway_bp = Blueprint("gateway", __name__)
limiter = Limiter(key_func=get_remote_address, default_limits=[])

MAX_BODY_BYTES = 10_000
REQUEST_TIMEOUT = 3

_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)


def _audit(event: str, outcome: str, **facts) -> None:
    """Write a single-line JSON audit event without secrets or unescaped newlines."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": str(event)[:64],
        "outcome": str(outcome)[:64],
    }
    record.update({k: str(v)[:64] for k, v in facts.items()})
    _audit_logger.info(json.dumps(record, ensure_ascii=True, separators=(",", ":")))


def error(code: str, message: str, status: int = 400):
    return jsonify(error=code, message=message), status


def _reject_json_constant(constant: str):
    raise ValueError(f"Unsupported JSON constant: {constant}")


def require_json_body() -> dict:
    raw = request.get_data(as_text=True)
    if not raw:
        raise ValueError("Request body must be a JSON object")
    try:
        body = json.loads(raw, parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise ValueError("Request body must be a valid JSON object") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def _auth_headers() -> dict:
    auth = request.headers.get("Authorization")
    return {"Authorization": auth} if auth else {}


def _safe_path_segment(value: str) -> str | None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or not value.isprintable()
        or "/" in value
        or "\\" in value
        or ".." in value
    ):
        return None
    return quote(value, safe="")


def _downstream_failure(response: requests.Response):
    try:
        payload = response.json()
        if isinstance(payload, dict) and "error" in payload and "message" not in payload:
            payload = {"error": "upstream_error", "message": str(payload["error"])}
        return jsonify(payload), response.status_code
    except ValueError:
        return error("upstream_error", "An internal service request failed", 502)


def forward(method: str, url: str, **kwargs):
    timeout = current_app.config.get("REQUEST_TIMEOUT", REQUEST_TIMEOUT)
    verify = current_app.config.get("CA_CERT_PATH", "/certs/ca.pem")
    try:
        res = requests.request(method, url, timeout=timeout, verify=verify, **kwargs)
        if res.status_code >= 400:
            return None, _downstream_failure(res)
        if res.content:
            return res.json(), None
        return {}, None
    except requests.Timeout:
        return None, error("upstream_timeout", "An internal service did not respond in time", 504)
    except (requests.RequestException, ValueError):
        return None, error("upstream_error", "An internal service request failed", 502)


def _proxy_json(method: str, url: str, status: int = 200, with_body: bool = False, with_auth: bool = True):
    kwargs = {}
    if with_auth:
        kwargs["headers"] = _auth_headers()
    if with_body:
        try:
            kwargs["json"] = require_json_body()
        except ValueError as exc:
            return error("invalid_request", str(exc), 400)

    data, failure = forward(method, url, **kwargs)
    if failure is not None:
        return failure
    return jsonify(data), status


@gateway_bp.post("/account")
@limiter.limit("20 per minute")
def proxy_account():
    return _proxy_json(
        "POST",
        f"{current_app.config['AUTH_URL']}/account",
        status=201,
        with_body=True,
        with_auth=False,
    )


@gateway_bp.post("/login")
@limiter.limit("20 per minute")
def proxy_login():
    return _proxy_json(
        "POST",
        f"{current_app.config['AUTH_URL']}/login",
        status=200,
        with_body=True,
        with_auth=False,
    )


@gateway_bp.get("/team")
def proxy_get_team():
    return _proxy_json("GET", f"{current_app.config['ENCOUNTER_URL']}/team")


@gateway_bp.put("/team")
def proxy_put_team():
    return _proxy_json("PUT", f"{current_app.config['ENCOUNTER_URL']}/team", with_body=True)


@gateway_bp.get("/challenges")
def proxy_get_challenges():
    return _proxy_json("GET", f"{current_app.config['ENCOUNTER_URL']}/challenges")


@gateway_bp.get("/encounters")
def proxy_get_history():
    return _proxy_json("GET", f"{current_app.config['ENCOUNTER_URL']}/encounters")


@gateway_bp.get("/encounters/<encounter_id>")
def proxy_get_encounter(encounter_id):
    safe_id = _safe_path_segment(encounter_id)
    if safe_id is None:
        return error("invalid_request", "Invalid encounter ID", 400)
    return _proxy_json("GET", f"{current_app.config['ENCOUNTER_URL']}/encounters/{safe_id}")


@gateway_bp.post("/encounters")
def proxy_post_encounters():
    return _proxy_json(
        "POST",
        f"{current_app.config['ENCOUNTER_URL']}/encounters",
        status=201,
        with_body=True,
    )


@gateway_bp.post("/encounters/<encounter_id>/action")
def proxy_post_encounter_action(encounter_id):
    safe_id = _safe_path_segment(encounter_id)
    if safe_id is None:
        return error("invalid_request", "Invalid encounter ID", 400)
    return _proxy_json(
        "POST",
        f"{current_app.config['ENCOUNTER_URL']}/encounters/{safe_id}/action",
        with_body=True,
    )


@gateway_bp.get("/monsters")
@limiter.limit("30 per minute")
def proxy_get_monsters():
    """Returns the complete catalog of the 16 monsters (US-10)."""
    return _proxy_json("GET", f"{current_app.config['MONSTER_URL']}/monsters", with_auth=False)


@gateway_bp.get("/monsters/<int:monster_id>")
def proxy_get_monster_details(monster_id):
    """Returns the details of a specific monster (US-11)."""
    return _proxy_json(
        "GET",
        f"{current_app.config['MONSTER_URL']}/monsters/{monster_id}",
        with_auth=False,
    )


@gateway_bp.get("/assets/monsters/<filename>")
def proxy_get_monster_asset(filename):
    """Serves monster artwork from the Monster Service (US-11)."""
    safe_name = _safe_path_segment(filename)
    if safe_name is None:
        return error("invalid_request", "Invalid asset filename", 400)

    url = f"{current_app.config['MONSTER_URL']}/assets/monsters/{safe_name}"
    timeout = current_app.config.get("REQUEST_TIMEOUT", REQUEST_TIMEOUT)
    verify = current_app.config.get("CA_CERT_PATH", "/certs/ca.pem")
    try:
        res = requests.get(url, timeout=timeout, verify=verify)
        if res.status_code >= 400:
            return _downstream_failure(res)
        return Response(
            res.content,
            status=res.status_code,
            content_type=res.headers.get("Content-Type", "application/octet-stream"),
        )
    except requests.Timeout:
        return error("upstream_timeout", "An internal service did not respond in time", 504)
    except requests.RequestException:
        return error("upstream_error", "An internal service request failed", 502)


@gateway_bp.get("/collection")
@limiter.limit("30 per minute")
def proxy_get_collection():
    """Returns the player's collection and performs Lazy Init on the first access (US-06, US-09)."""
    return _proxy_json("GET", f"{current_app.config['MONSTER_URL']}/collection")


@gateway_bp.get("/health")
def health():
    return jsonify(status="ok"), 200


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        AUTH_URL=os.environ.get("AUTH_URL", "https://player-service:5001").rstrip("/"),
        MONSTER_URL=os.environ.get("MONSTER_URL", "https://monster-service:5002").rstrip("/"),
        ENCOUNTER_URL=os.environ.get("ENCOUNTER_URL", "https://encounter-service:5003").rstrip("/"),
        CA_CERT_PATH=os.environ.get("CA_CERT_PATH", "/certs/ca.pem"),
        FRONTEND_ORIGIN=os.environ.get("FRONTEND_ORIGIN", "http://localhost:8080"),
        REQUEST_TIMEOUT=float(os.environ.get("REQUEST_TIMEOUT", REQUEST_TIMEOUT)),
        MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
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
    def add_cors_and_audit(response):
        response.headers["Access-Control-Allow-Origin"] = current_app.config["FRONTEND_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"

        if request.path != "/health":
            status = response.status_code
            outcome = (
                "success"
                if status < 400
                else "denied"
                if status in (401, 403, 429)
                else "failure"
            )
            _audit(
                "gateway_request",
                outcome,
                ip=request.remote_addr or "-",
                method=request.method,
                path=request.path,
                status=status,
            )
        return response

    @app.errorhandler(429)
    def handle_rate_limit_exceeded(_error):
        return error("rate_limit_exceeded", "Too many requests", 429)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return error(exc.name.lower().replace(" ", "_"), exc.description, exc.code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(_exc):
        return error("server_error", "An unexpected error occurred", 500)

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=5005,
        ssl_context=("/certs/server.pem", "/certs/server.key"),
    )
