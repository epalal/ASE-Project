import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from flask import Flask, jsonify, g, request
from .models import db, get_fernet, migrate_legacy_player_ids
from .routes.monsters import monsters_bp
from app.audit import audit

def read_secret(secret_name, default=None):
    """Reads a secret from the Docker secrets directory. If the secret is not found, returns the default value."""
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return default

def resolve_database_url():
    """Builds the SQLAlchemy database URI using DATABASE_URL if provided, injecting the Docker secret password if needed."""
    db_password = read_secret("db_password", "postgres")
    raw_db_url = os.environ.get("DATABASE_URL")

    if not raw_db_url:
        raw_db_url = f"postgresql://postgres:{db_password}@monster_db:5432/monster_db"

    parsed = urlparse(raw_db_url)
    if not parsed.scheme.startswith("postgres"):
        return raw_db_url

    if not parsed.password:
        username = parsed.username or "postgres"
        hostname = parsed.hostname or "monster_db"
        netloc = f"{username}:{db_password}@{hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        parsed = parsed._replace(netloc=netloc)

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "verify-full"
    query.setdefault(
        "sslrootcert",
        os.environ.get("DATABASE_SSL_ROOT_CERT", "/certs/ca.pem"),
    )
    return urlunparse(parsed._replace(query=urlencode(query)))

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=resolve_database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    if test_config:
        app.config.update(test_config)

    get_fernet()
    db.init_app(app)
    app.register_blueprint(monsters_bp)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "service": "monster_service"}), 200

    with app.app_context():
        db.create_all()
        migrate_legacy_player_ids()
        from .initial_monsters import init_catalog
        init_catalog()

    @app.after_request
    def audit_request(response):
        if request.path == "/health":
            return response
        status = response.status_code
        outcome = (
            "success"
            if status < 400
            else "denied"
            if status in (401, 403)
            else "failure"
        )
        user = getattr(g, "player_id", None) or getattr(g, "username", None) or "-"
        audit(
            "request",
            outcome,
            user=user,
            method=request.method,
            path=request.path,
            status=status,
        )
        return response

    return app