import logging
import os

from flask import Blueprint, Flask, jsonify, send_from_directory, send_file

gateway_bp = Blueprint("frontend", __name__)

_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)


app = Flask(__name__)
@app.get("/health")
def health():
    return jsonify(status="ok"), 200

@app.get("/")
def index():
    return send_file("files/index.html"), 200

@app.get("/<path:filename>")
def serve_file(filename):
    return send_from_directory("files", filename)


def create_app(test_config=None): 
    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=8080,
        ssl_context=("/certs/server.pem", "/certs/server.key"),
    )
