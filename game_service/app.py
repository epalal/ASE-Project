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
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f)
    except Exception:
        pass

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

@app.post('/game_service')
def game_service():
    try:
        body = require_json_body()
        operation_type = body.get("operation_type")
        if operation_type not in ["enter_game", "game_progress", "characters"]:
            return error("invalid_operation", "Invalid operation type")

        arguments = require_arguments(body, 1)
        username = arguments[0]

        if operation_type == "enter_game":
            if username not in users_db:
                return error("unauthorized", "Invalid or missing username", status=401)

            user_data = users_db[username]
            return jsonify(
                message="Welcome to the game!",
                progress=user_data["progress"],
                characters=user_data["characters"]
            ), 200

        elif operation_type == "game_progress":
            progress = body.get("progress")
            if not isinstance(progress, dict):
                return error("invalid_input", "Progress must be a JSON object")

            if username not in users_db:
                return error("unauthorized", "Invalid or missing username", status=401)

            users_db[username]["progress"].update(progress)
            
            with open(DATA_FILE, 'w') as f:
                json.dump(users_db, f)

            return jsonify(message="Progress updated successfully"), 200

        elif operation_type == "characters":
            character = body.get("character")
            if not isinstance(character, dict) or "name" not in character or "type" not in character:
                return error("invalid_input", "Character must be a JSON object with 'name' and 'type'")

            if username not in users_db:
                return error("unauthorized", "Invalid or missing username", status=401)

            users_db[username]["characters"].append(character)
            
            with open(DATA_FILE, 'w') as f:
                json.dump(users_db, f)

            return jsonify(message="Character added successfully"), 200

    except ValueError as e:
        app.logger.error(f"ValueError: {str(e)}")
        return error("invalid_request", str(e))
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return error("server_error", "An unexpected error occurred")

@app.get('/health')
def health():
    return jsonify(status="healthy"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)