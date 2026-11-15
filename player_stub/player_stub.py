import time
from flask import Flask, jsonify, request

app = Flask(__name__)

calls = []
users = {}

@app.post("/account")
def account():
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify(error="invalid_input", message="Request body must be a valid JSON object"), 400

    username = body.get("username")
    password = body.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="invalid_input", message="Username and password must be strings"), 400

    calls.append({"endpoint": "/account", "body": body})

    if username == "error_server":
        return jsonify(error="server_error", message="Could not save user data"), 500

    if username in users:
        return jsonify(error="user_exists", message="Username already exists"), 409

    user_id = "123e4567-e89b-12d3-a456-426614174000"
    users[username] = {"id": user_id, "password": password}

    return jsonify(
        message="Account created successfully",
        username=username,
        id=user_id
    ), 201

@app.post("/login")
def login():
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify(error="invalid_input", message="Request body must be a valid JSON object"), 400

    username = body.get("username")
    password = body.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="invalid_input", message="Username and password must be strings"), 401

    calls.append({"endpoint": "/login", "body": body})

    user = users.get(username)
    if not user or user["password"] != password:
        return jsonify(error="unauthorized", message="Invalid username or password"), 401

    return jsonify(
        message="Successful login",
        username=username,
        id=user["id"],
        token="123e4567-e89b-12d3-a456-426614174001"
    ), 200

@app.get("/health")
def health():
    return jsonify(status="healthy"), 200

@app.get("/_calls")
def received():
    """Useful endpoint for tests, responds with calls received by the stub."""
    return jsonify(calls), 200

@app.post("/_reset")
def reset():
    """Clears stub state before each test."""
    calls.clear()
    users.clear()
    return jsonify(calls=0), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, ssl_context=("/certs/server.pem", "/certs/server.key"))