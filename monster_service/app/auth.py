import os
from functools import wraps
from flask import request, jsonify, g
import jwt

def get_public_key():
    # Può essere passata come variabile d'ambiente o letta da un file montato via Docker
    pub_key = os.environ.get("JWT_PUBLIC_KEY")
    if pub_key:
        return pub_key.replace("\\n", "\n")
    key_path = os.environ.get("JWT_PUBLIC_KEY_PATH", "/certs/jwt_public.pem")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read()
    raise RuntimeError("Public key per RS256 non configurata.")

def require_jwt(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token mancante o formato Bearer non valido"}), 401
        
        token = auth_header.split(" ", 1)[1].strip()
        try:
            public_key = get_public_key()
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            # Concorda con Developer 1 se usa 'sub' o 'player_id'
            player_id = payload.get("sub") or payload.get("player_id")
            if not player_id:
                return jsonify({"error": "Payload del token privo di identificativo giocatore"}), 401
            g.player_id = str(player_id)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token scaduto"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token non valido"}), 401
        
        return f(*args, **kwargs)
    return decorated

def require_internal_secret(f):
    """Protegge le rotte interne (es. /internal/rewards) affinché solo Encounter Service possa chiamarle."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected_secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        provided_secret = request.headers.get("X-Internal-Secret")
        if not expected_secret or provided_secret != expected_secret:
            return jsonify({"error": "Accesso non autorizzato: endpoint riservato ai microservizi interni"}), 403
        return f(*args, **kwargs)
    return decorated