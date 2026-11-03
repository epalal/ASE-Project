from flask import Flask, jsonify, request
import json
import os
import atexit

DATA_FILE = "/app/data/users_data.json"
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r') as f:
            users_db = json.load(f)
    except json.JSONDecodeError:
        users_db = {}
else:
    users_db = {}

@atexit.register
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(users_db, f)

app = Flask(__name__)

def error(code, message, status=400):
    return jsonify(error=code, message=message), status

def require_json_body():
    body = request.get_json(silent=True)
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

@app.post('/create_account')
def create_account():
    try:
        body = require_json_body()
        arguments = require_arguments(body, 2)
        username, password = arguments

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings")

        if username in users_db:
            return error("user_exists", "Username already exists", status=409)

        users_db[username] = {
            "password": password,
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

        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f)

        return jsonify(message="Account created successfully", username=username), 201

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception as e:
        return error("server_error", "An unexpected error occurred")

@app.post('/login')
def login():
    try:
        body = require_json_body()
        arguments = require_arguments(body, 2)
        username, password = arguments

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings")

        if username not in users_db or users_db[username]["password"] != password:
            return error("unauthorized", "Invalid username or password", status=401)

        return jsonify(message="Login successful", username=username), 200

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception as e:
        return error("server_error", "An unexpected error occurred")

@app.get('/health')
def health():
    return jsonify(status="healthy"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)