from flask import Flask, jsonify, request
import json
import os
import atexit
import tempfile
import threading
import traceback
import uuid
import jwt
import time
from datetime import datetime, timezone
from db.db import SessionLocal, User
from bcrypt import hashpw, gensalt, checkpw

app = Flask(__name__)

PRIVATE_KEY_PATH = "/certs/jwt_private.pem"
PUBLIC_KEY_PATH = "/certs/jwt_public.pem"

def get_keys():
    try:
        with open(PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()
        with open(PUBLIC_KEY_PATH, 'r') as f:
            public_key = f.read()
        return private_key, public_key
    except FileNotFoundError:
        return None, None

db_lock = threading.Lock()

def error(code, message, status=400):
    return jsonify(error=code, message=message), status

def require_json_body():
    body = request.get_json(silent=True)
    if body is None:
        raise ValueError("Request body must be a valid JSON object")
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body

def require_arguments(body, expected_count):
    arguments = body.get("arguments")
    if not isinstance(arguments, list):
        raise ValueError("'arguments' must be a JSON array")
    if len(arguments) != expected_count:
        raise ValueError(f"Expected {expected_count} argument(s)")
    return arguments

@app.post('/account')
def account():
    session = SessionLocal()
    try:
        body = require_json_body()

        username = body.get("username")
        password = body.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings")

        existing_user = session.query(User).filter_by(username=username).first()

        if existing_user:
            return error("user_exists", "Username already exists", status=409)

        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
        new_user = User(
            username=username,
            password_hashed=hashed_password,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        
        session.add(new_user)
        session.commit()

        return jsonify(message="Account created successfully"), 201

    except ValueError as e:
        session.rollback()
        return error("invalid_request", str(e))
    except Exception:
        session.rollback()
        traceback.print_exc()
        return error("server_error", "An unexpected error occurred", status=500)
    finally:
        session.close()

@app.post('/login')
def login():
    session = SessionLocal()
    try:
        body = require_json_body()
        username = body.get("username")
        password = body.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings", status=401)
        
        user = session.query(User).filter_by(username=username).first()

        if not user or not checkpw(password.encode('utf-8'), user.password_hashed.encode('utf-8')):
            return error("unauthorized", "Invalid username or password", status=401)
        
        private_key, _ = get_keys()
        if not private_key:
            return error("server_error", "JWT signing keys not available", status=500)

        token = jwt.encode(
            {
                "sub": user.id, 
                "aud": "monster-tamers", 
                "iss": "player-service",
                "exp": int(time.time()) + 3600,
                "username": username
            },
            private_key,
            algorithm="RS256"
        )

        session.close()
        return jsonify(message="Successful login", username=username, id=user.id, token=token), 200

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception:
        traceback.print_exc()
        return error("server_error", "An unexpected error occurred", status=500)
    finally:
        session.close()

@app.get('/health')
def health():
    return jsonify(status="healthy"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, ssl_context=("/certs/server.pem", "/certs/server.key"))