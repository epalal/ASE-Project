import os
from urllib.parse import urlparse, urlunparse
from flask import Flask, send_from_directory, jsonify
from sqlalchemy.exc import IntegrityError, OperationalError 
from .models import db
from .routes.monsters import monsters_bp

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
        return f"postgresql://postgres:{db_password}@monster_db:5432/monster_db"

    parsed = urlparse(raw_db_url)
    if not parsed.password and parsed.scheme.startswith("postgres"):
        username = parsed.username or "postgres"
        hostname = parsed.hostname or "monster_db"
        netloc = f"{username}:{db_password}@{hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))

    return raw_db_url

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=resolve_database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    app.register_blueprint(monsters_bp)

    @app.route('/assets/monsters/<path:filename>')
    def serve_monster_images(filename):
        return send_from_directory('static/assets/monsters', filename)
     
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "service": "monster_service"}), 200

    with app.app_context():
        try:
            db.create_all()
        except (IntegrityError, OperationalError):
            db.session.rollback()
        from .initial_monsters import init_catalog
        init_catalog()

    return app