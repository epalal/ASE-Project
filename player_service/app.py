from datetime import datetime, timezone
import json
import logging
import os
import time

from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, current_app, g, jsonify, request
import jwt
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from db.db import User, db

MAX_BODY_BYTES = 10_000
MAX_USERNAME_LENGTH = 64
MIN_PASSWORD_LENGTH = 4
MAX_PASSWORD_BYTES = 72  # bcrypt silently truncates beyond 72 bytes
TOKEN_TTL_SECONDS = 15 * 60
JWT_ISSUER = "player-service"
JWT_AUDIENCE = "monster-tamers"

_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)


def _audit(event: str, outcome: str, user: str = "-", **facts) -> None:
    """Write a single-line JSON audit event without secrets or unescaped newlines."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": str(event)[:64],
        "user": (str(user) if user else "-")[:64],
        "outcome": str(outcome)[:64],
    }
    record.update({k: str(v)[:64] for k, v in facts.items()})
    _audit_logger.info(json.dumps(record, ensure_ascii=True, separators=(",", ":")))


def error(code: str, message: str, status: int = 400):
    return jsonify(error=code, message=message), status


def _reject_json_constant(constant: str):
    raise ValueError(f"Unsupported JSON constant: {constant}")


def _require_json_object():
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


def _validate_credentials(body: dict):
    username = body.get("username")
    password = body.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("Username and password must be strings")
    if (
        not 1 <= len(username) <= MAX_USERNAME_LENGTH
        or username != username.strip()
        or not username.isprintable()
        or any(ch.isspace() for ch in username)
    ):
        raise ValueError(
            "Username must be 1 to 64 printable characters with no spaces or control characters"
        )
    if (
        len(password) < MIN_PASSWORD_LENGTH
        or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in password)
    ):
        raise ValueError(
            f"Password must be {MIN_PASSWORD_LENGTH} characters to {MAX_PASSWORD_BYTES} bytes with no control characters"
        )
    return username, password


def _load_private_key(app_config) -> str | None:
    if app_config.get("JWT_PRIVATE_KEY"):
        return app_config["JWT_PRIVATE_KEY"]
    path = app_config.get("JWT_PRIVATE_KEY_PATH")
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as key_file:
            return key_file.read()
    return None


def create_app(test_config=None):
    app = Flask(__name__)
    database_url = os.environ.get("DATABASE_URL")
    if test_config is None and not database_url:
        raise RuntimeError("DATABASE_URL must be set before starting the Player Service")

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=database_url or "sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
        JWT_PRIVATE_KEY=os.environ.get("JWT_PRIVATE_KEY", "").replace("\\n", "\n") or None,
        JWT_PRIVATE_KEY_PATH=os.environ.get("JWT_PRIVATE_KEY_PATH", "/certs/jwt_private.pem"),
        TOKEN_TTL_SECONDS=int(os.environ.get("TOKEN_TTL_SECONDS", TOKEN_TTL_SECONDS)),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            db.engine.dispose()

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return error(exc.name.lower().replace(" ", "_"), exc.description, exc.code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(_exc):
        db.session.rollback()
        return error("server_error", "An unexpected error occurred", 500)

    @app.after_request
    def audit_request(response):
        if request.path == "/health":
            return response
        status = response.status_code
        outcome = (
            "success"
            if status < 400
            else "denied"
            if status in (401, 403)
            else "failure"
        )
        _audit(
            "request",
            outcome,
            user=getattr(g, "audit_user", "-"),
            method=request.method,
            path=request.path,
            status=status,
        )
        return response

    @app.post("/account")
    def account():
        try:
            body = _require_json_object()
            username, password = _validate_credentials(body)
        except ValueError as exc:
            return error("invalid_input", str(exc), 400)

        g.audit_user = username
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return error("user_exists", "Username already exists", 409)

        hashed_password = hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")
        new_user = User(username=username, password_hashed=hashed_password)
        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return error("user_exists", "Username already exists", 409)

        return (
            jsonify(
                message="Account created successfully",
                username=new_user.username,
                id=new_user.id,
            ),
            201,
        )

    @app.post("/login")
    def login():
        try:
            body = _require_json_object()
            username, password = _validate_credentials(body)
        except ValueError as exc:
            return error("invalid_input", str(exc), 400)

        g.audit_user = username
        user = User.query.filter_by(username=username).first()
        if not user or not checkpw(
            password.encode("utf-8"), user.password_hashed.encode("utf-8")
        ):
            return error("unauthorized", "Invalid username or password", 401)

        private_key = _load_private_key(current_app.config)
        if not private_key:
            return error("server_error", "JWT signing keys not available", 500)

        now = int(time.time())
        payload = {
            "iss": JWT_ISSUER,
            "sub": str(user.id),
            "aud": JWT_AUDIENCE,
            "username": user.username,
            "iat": now,
            "exp": now + current_app.config["TOKEN_TTL_SECONDS"],
        }
        token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers={"alg": "RS256", "typ": "JWT"},
        )
        g.audit_user = str(user.id)
        return (
            jsonify(
                message="Successful login",
                username=user.username,
                id=user.id,
                token=token,
            ),
            200,
        )

    @app.get("/health")
    def health():
        return jsonify(status="healthy"), 200

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=5001,
        ssl_context=("/certs/server.pem", "/certs/server.key"),
    )
