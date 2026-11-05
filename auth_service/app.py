from flask import Flask, jsonify, request
import json
import os
import atexit
import tempfile
import threading
import traceback
import uuid
from bcrypt import hashpw, gensalt, checkpw

app = Flask(__name__)

BASE_DIR = "/app"
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "users_data.json")
SESSION_FILE = os.path.join(DATA_DIR, "session_tokens.json")

db_lock = threading.Lock()

session_tokens = {}

os.makedirs(DATA_DIR, exist_ok=True)
print(f"[auth_service] File: {DATA_FILE}")

if not os.path.exists(DATA_FILE):
    users_db = {}
else:
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            users_db = json.load(f)
        if not isinstance(users_db, dict):
            print("[auth_service] File doesn't contain a JSON object.")
            users_db = {}
    except json.JSONDecodeError:
        print("[auth_service] File is not valid.")
        users_db = {}

if os.path.exists(SESSION_FILE):
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            session_tokens = json.load(f)
    except json.JSONDecodeError:
        app.logger.error("[auth_service] Error while reading file session_tokens.json")
        session_tokens = {}
else:
    session_tokens = {}

def save_users_to_file():
    with db_lock:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(users_db, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, DATA_FILE)
            return True
        except Exception:
            print(f"[auth_service] Error during the save of {DATA_FILE}")
            traceback.print_exc()
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False
        
def save_session_tokens():
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(session_tokens, f, indent=4)
    except Exception as e:
        app.logger.error(f"Error while saving session token: {str(e)}")

@atexit.register
def save_data():
    if not save_users_to_file():
        print("[auth_service] Final save didn't worked.")

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
    try:
        body = require_json_body()

        username = body.get("username")
        password = body.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings")

        if username in users_db:
            return error("user_exists", "Username already exists", status=409)

        user_id = str(uuid.uuid4())
        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

        users_db[username] = {
            "id": user_id,
            "password": hashed_password,
            "progress": {
                "level": 1,
                "experience": 0
            },
            "characters": [
                {"name": "FireDragon", "type": "fire", "level": 1},
                {"name": "WaterPhoenix", "type": "water", "level": 1},
                {"name": "EarthGolem", "type": "earth", "level": 1}
            ]
        }

        if not save_users_to_file():
            users_db.pop(username, None)
            return error("server_error", "Could not save user data", status=500)

        return jsonify(message="Account created successfully", username=username, id=user_id), 201

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception:
        traceback.print_exc()
        return error("server_error", "An unexpected error occurred", status=500)

@app.post('/login')
def login():
    try:
        body = require_json_body()
        username = body.get("username")
        password = body.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            session_tokens.clear()
            save_session_tokens()
            return error("invalid_input", "Username and password must be strings")

        user = users_db.get(username)
        if not user or not checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            session_tokens.clear()
            save_session_tokens()
            return error("unauthorized", "Invalid username or password", status=401)

        token = str(uuid.uuid4())

        session_tokens.clear()
        session_tokens[token] = username

        save_session_tokens()

        return jsonify(message="Successful login", username=username, id=user["id"], token=token), 200

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception:
        traceback.print_exc()
        return error("server_error", "An unexpected error occurred", status=500)

@app.get('/health')
def health():
    return jsonify(status="healthy"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)