from flask import Flask, jsonify, request
import json
import os
import atexit

app = Flask(__name__)

BASE_DIR = "/app"
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "users_data.json")
SESSION_FILE = os.path.join(DATA_DIR, "session_tokens.json")

os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            users_db = json.load(f)
            if not isinstance(users_db, dict):
                raise ValueError("File doesn't contain a valid JSON object.")
    except (json.JSONDecodeError, ValueError) as e:
        app.logger.error(f"Error while reading file {DATA_FILE}: {str(e)}")
        users_db = {}
else:
    app.logger.warning(f"File {DATA_FILE} doesn't exist. Initializing an empty file.")
    users_db = {}

if os.path.exists(SESSION_FILE):
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            session_tokens = json.load(f)
    except json.JSONDecodeError as e:
        app.logger.error(f"Errore while reading file {SESSION_FILE}: {str(e)}")
        session_tokens = {}
else:
    session_tokens = {}

@atexit.register
def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f)
    except Exception:
        pass

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

def validate_session_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise ValueError("Missing session token")
    
    token = auth_header.replace("Bearer ", "").strip()
    
    current_tokens = {}
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                current_tokens = json.load(f)
        except json.JSONDecodeError as e: 
            app.logger.error(f"Error while reading file session_tokens.json: {str(e)}")
    
    if token not in current_tokens:
        raise ValueError("Invalid session token")
        
    return current_tokens[token]

@app.post('/statistics')
def statistics():
    try:
        validate_session_token()

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