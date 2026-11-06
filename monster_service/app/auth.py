import os
from functools import wraps
from flask import request, jsonify, g
import jwt

JWT_ALGORITHM = "RS256"

def get_public_key():
    pub_key = os.environ.get("JWT_PUBLIC_KEY")
    if pub_key:
        return pub_key.replace("\\n", "\n")
    key_path = os.environ.get("JWT_PUBLIC_KEY_PATH", "/certs/jwt_public.pem")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read()
    raise RuntimeError(f"Public key {JWT_ALGORITHM} not found.")

def require_jwt(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Bearer token"}), 401
        
        token = auth_header.split(" ", 1)[1].strip()
        try:
            public_key = get_public_key()
            payload = jwt.decode(token, public_key, algorithms=[JWT_ALGORITHM])
            # !!!!!!!!!Concorda con Developer 1 se usa 'sub' o 'player_id'!!!!!!!!!!
            player_id = payload.get("sub") or payload.get("player_id")
            if not player_id:
                return jsonify({"error": "Payload of the token is missing player identifier"}), 401
            g.player_id = str(player_id)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token is invalid"}), 401
        
        return f(*args, **kwargs)
    return decorated

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