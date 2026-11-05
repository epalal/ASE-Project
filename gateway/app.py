import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:5001").rstrip("/")
GAME_URL = os.environ.get("GAME_URL", "http://localhost:5002").rstrip("/")
REQUEST_TIMEOUT = 3

def error(code, message, status=400):
    return jsonify(error=code, message=message), status

def require_json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body

def downstream_failure(response):
    try:
        return jsonify(response.json()), response.status_code
    except ValueError:
        return error("upstream_error", "An internal service request failed", 502)

def forward(method, url, **kwargs):
    try:
        res = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
        if res.status_code >= 400:
            return None, downstream_failure(res)
        
        if res.content:
            data = res.json()
            if not isinstance(data, dict):
                raise ValueError("Internal service returned non-object JSON")
            return data, None
        return {}, None

    except requests.Timeout:
        return None, error("upstream_timeout", "An internal service did not respond in time", 504)
    except (requests.RequestException, ValueError):
        return None, error("upstream_error", "An internal service request failed", 502)

@app.post("/account")
def proxy_account():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/account", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 201

@app.post("/login")
def proxy_login():
    try:
        body = require_json_body()
    except ValueError as exc:
        return error("invalid_request", str(exc))

    data, failure = forward("POST", f"{AUTH_URL}/login", json=body)
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/statistics")
def proxy_statistics():
    username = request.args.get('username')
    auth_header = request.headers.get('Authorization')
    
    if not username:
        return error("invalid_request", "Missing username", 400)
    
    payload = {
        "operation_type": "enter_game",
        "arguments": [username]
    }
    
    headers = {"Authorization": auth_header} if auth_header else {}
    data, failure = forward("POST", f"{GAME_URL}/statistics", json=payload, headers=headers)
    
    if failure is not None:
        return failure
    return jsonify(data), 200

@app.get("/")
def home():
    return '''
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <title>Microservice Gateway</title>
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
        <div class="card">
            <h2>Create an Account</h2>
            <form id="createForm">
                <label>Username:</label>
                <input type="text" id="reg-username" required>
                <label>Password:</label>
                <input type="password" id="reg-password" required>
                <button type="submit" class="btn-green">Register</button>
            </form>
            <div id="reg-result" class="result"></div>
        </div>

        <div class="card">
            <h2>Login</h2>
            <form id="loginForm">
                <label>Username:</label>
                <input type="text" id="login-username" required>
                <label>Password:</label>
                <input type="password" id="login-password" required>
                <button type="submit" class="btn-blue">Access</button>
            </form>
            <div id="login-result" class="result"></div>
        </div>

        <div class="card">
            <h2>Welcome</h2>
            <button id="viewGame" class="btn-blue">Show progress and Monsters</button>
            <div id="game-result" class="result"></div>
        </div>

        <script>
            let loggedInUser = null;
            let authToken = null;

            document.getElementById('createForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const username = document.getElementById('reg-username').value;
                const password = document.getElementById('reg-password').value;

                const response = await fetch('/account', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, password: password })
                });

                const data = await response.json();
                const resultDiv = document.getElementById('reg-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = data.message + ' (User: ' + data.username + ')';
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Error: ' + (data.message || data.error);
                }
            });

            document.getElementById('loginForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, password: password })
                });

                const data = await response.json();
                const resultDiv = document.getElementById('login-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = data.message;
                    loggedInUser = data.username;
                    authToken = data.token;
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Error: ' + (data.message || data.error);
                }
            });

            document.getElementById('viewGame').addEventListener('click', async function() {
                if (!loggedInUser || !authToken) {
                    alert("You have to login first.");
                    return;
                }

                const response = await fetch(`/statistics?username=${loggedInUser}`, {
                    headers: { 'Authorization': authToken }
                });
                const data = await response.json();
                const resultDiv = document.getElementById('game-result');
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.innerText = `Progress: Level ${data.progress.level}, Experience ${data.progress.experience}\\n` +
                                        'Characters: ' + data.characters.map(c => c.name).join(', ');
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.innerText = 'Error: ' + (data.message || data.error);
                }
            });
        </script>
    </body>
    </html>
    ''', 200

@app.get("/health")
def health():
    return jsonify(status="ok"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)