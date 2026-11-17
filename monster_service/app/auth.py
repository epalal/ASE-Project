import os
from functools import wraps
import hmac
import jwt
from flask import request, jsonify, g

def _load_public_key():
    # Supporta sia il percorso del compose principale (/certs/jwt_public.pem)
    # sia il secret standalone (/run/secrets/jwt_public) o variabile d'ambiente
    for path in (
        os.environ.get("JWT_PUBLIC_KEY_PATH", ""),
        "/certs/jwt_public.pem",
        "/run/secrets/jwt_public",
    ):
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return os.environ.get("JWT_PUBLIC_KEY")

def _unauthorized(message="Invalid or missing token"):
    resp = jsonify({"error": "unauthorized", "message": message})
    resp.status_code = 401
    resp.headers["WWW-Authenticate"] = "Bearer"
    return resp

def require_jwt(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return _unauthorized("Missing bearer token")

        public_key = _load_public_key()
        if not public_key:
            return jsonify({"error": "server_error", "message": "JWT public key not configured"}), 500

        try:
            claims = jwt.decode(
                token.strip(),
                public_key,
                algorithms=["RS256"],
                issuer="player-service",
                options={"require": ["exp", "iss", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            return _unauthorized("Token expired")
        except jwt.InvalidTokenError:
            return _unauthorized("Invalid token")

        player_id = str(claims.get("sub", "")).strip()
        if not player_id:
            return _unauthorized("Invalid subject in token")

        g.player_id = player_id
        g.username = claims.get("username")
        return fn(*args, **kwargs)

    return wrapper

def require_internal_secret(f):
    """Protects internal routes (es. /internal/rewards) from unauthorized access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        provided_secret = request.headers.get("X-Internal-Secret")
        if not expected_secret or provided_secret != expected_secret:
            return jsonify({"error": "Access denied: invalid internal secret"}), 403
        return f(*args, **kwargs)
    return decorated