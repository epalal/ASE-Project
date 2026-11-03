from flask import Flask, jsonify, request
import json
import os

DATA_FILE = "users_data.json"

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r') as f:
            users_db = json.load(f)
    except json.JSONDecodeError:
        users_db = {}
else:
    users_db = {}

# Salva i dati su file alla chiusura del server
import atexit
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

# Interfaccia HTML per testare sia Registrazione che Login da browser
@app.route('/', methods=['GET'])
def home():
    return '''
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <title>Microservizio Auth</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .card { max-width: 400px; padding: 20px; border: 1px solid #ccc; border-radius: 8px; margin-bottom: 20px; }
            input { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; }
            button { width: 100%; padding: 10px; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .btn-green { background-color: #28a745; }
            .btn-blue { background-color: #007bff; }
            .result { margin-top: 10px; font-weight: bold; }
        </style>
    </head>
    <body>
        <!-- Modulo Registrazione -->
        <div class="card">
            <h2>Crea Account</h2>
            <form id="createForm">
                <label>Username:</label>
                <input type="text" id="reg-username" required>
                <label>Password:</label>
                <input type="password" id="reg-password" required>
                <button type="submit" class="btn-green">Invia Registrazione</button>
            </form>
            <div id="reg-result" class="result"></div>
        </div>

        <!-- Modulo Login -->
        <div class="card">
            <h2>Effettua Login</h2>
            <form id="loginForm">
                <label>Username:</label>
                <input type="text" id="login-username" required>
                <label>Password:</label>
                <input type="password" id="login-password" required>
                <button type="submit" class="btn-blue">Accedi</button>
            </form>
            <div id="login-result" class="result"></div>
        </div>

        <script>
            // Gestione Registrazione
            document.getElementById('createForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const username = document.getElementById('reg-username').value;
                const password = document.getElementById('reg-password').value;

                const response = await fetch('/create_account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ arguments: [username, password] })
                });

                const data = await response.json();
                const resultDiv = document.getElementById('reg-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = data.message + ' (Utente: ' + data.username + ')';
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Errore: ' + (data.message || data.error);
                }
            });

            // Gestione Login
            document.getElementById('loginForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ arguments: [username, password] })
                });

                const data = await response.json();
                const resultDiv = document.getElementById('login-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = data.message;
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Errore: ' + (data.message || data.error);
                }
            });
        </script>

        <div class="card">
            <h2>Benvenuto nel Gioco</h2>
            <button id="viewGame" class="btn-blue">Visualizza Progressi e Personaggi</button>
            <div id="game-result" class="result"></div>
        </div>

        <script>
            document.getElementById('viewGame').addEventListener('click', async function() {
                const username = document.getElementById('login-username').value;

                const response = await fetch(`/game?username=${username}`);
                const data = await response.json();
                const resultDiv = document.getElementById('game-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = `Progressi: Livello ${data.progress.level}, Esperienza ${data.progress.experience}\n` +
                                        `Personaggi: ${data.characters.map(c => c.name).join(', ')}`;
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Errore: ' + (data.message || data.error);
                }
            });
        </script>

    </body>
    </html>
    ''', 200

@app.post('/player_service')
def player_service():
    try:
        body = require_json_body()
        operation_type = body.get("operation_type")
        if operation_type not in ["create_account", "login"]:
            return error("invalid_operation", "Invalid operation type")

        arguments = require_arguments(body, 2)
        username, password = arguments

        if not isinstance(username, str) or not isinstance(password, str):
            return error("invalid_input", "Username and password must be strings")

        if operation_type == "create_account":
            if username in users_db:
                return error("user_exists", "Username already exists", status=409)

            # Inizializza i dati dell'utente
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

            return jsonify(message="Account created successfully", username=username), 201

        elif operation_type == "login":
            # Controlla se l'utente esiste e la password corrisponde
            if username not in users_db or users_db[username]["password"] != password:
                return error("unauthorized", "Invalid username or password", status=401)

            return jsonify(message="Login successful", username=username), 200

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception as e:
        return error("server_error", "An unexpected error occurred")

@app.post('/player_service')
def player_service():
    try:
        body = require_json_body()
        operation_type = body.get("operation_type")
        if operation_type not in ["create_account", "login", "enter_game", "game_progress", "characters"]:
            return error("invalid_operation", "Invalid operation type")

        arguments = require_arguments(body, 2 if operation_type in ["create_account", "login"] else 1)
        username = arguments[0]

        if operation_type in ["create_account", "login"]:
            password = arguments[1]
            if not isinstance(username, str) or not isinstance(password, str):
                return error("invalid_input", "Username and password must be strings")

            if operation_type == "create_account":
                if username in users_db:
                    return error("user_exists", "Username already exists", status=409)

                # Inizializza i dati dell'utente
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

                return jsonify(message="Account created successfully", username=username), 201

            elif operation_type == "login":
                # Controlla se l'utente esiste e la password corrisponde
                if username not in users_db or users_db[username]["password"] != password:
                    return error("unauthorized", "Invalid username or password", status=401)

                return jsonify(message="Login successful", username=username), 200

        elif operation_type == "enter_game":
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
            return jsonify(message="Progress updated successfully"), 200

        elif operation_type == "characters":
            character = body.get("character")
            if not isinstance(character, dict) or "name" not in character or "type" not in character:
                return error("invalid_input", "Character must be a JSON object with 'name' and 'type'")

            if username not in users_db:
                return error("unauthorized", "Invalid or missing username", status=401)

            users_db[username]["characters"].append(character)
            return jsonify(message="Character added successfully"), 200

    except ValueError as e:
        return error("invalid_request", str(e))
    except Exception as e:
        return error("server_error", "An unexpected error occurred")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)