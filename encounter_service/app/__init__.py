import os
import secrets

from flask import Flask, jsonify

from .errors import register_error_handlers
from .models import db


class StartupError(RuntimeError):
    """The service cannot start because a setting is missing."""


def _settings_from_environment():
    """Read the settings Docker Compose passes in, and name every missing one."""
    env = os.environ
    public_key = env.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
    if not public_key and env.get("JWT_PUBLIC_KEY_PATH"):
        with open(env["JWT_PUBLIC_KEY_PATH"], encoding="utf-8") as key_file:
            public_key = key_file.read()
    settings = {
        "SQLALCHEMY_DATABASE_URI": env.get("DATABASE_URL"),
        "JWT_PUBLIC_KEY": public_key,
        "MONSTER_SERVICE_URL": env.get("MONSTER_SERVICE_URL"),
        "INTERNAL_SERVICE_SECRET": env.get("INTERNAL_SERVICE_SECRET"),
        "CA_CERT_PATH": env.get("CA_CERT_PATH"),
    }
    if env.get("JWT_ISSUER"):
        settings["JWT_ISSUER"] = env["JWT_ISSUER"]
    if env.get("JWT_AUDIENCE"):
        settings["JWT_AUDIENCE"] = env["JWT_AUDIENCE"]

    required = {
        "DATABASE_URL": "SQLALCHEMY_DATABASE_URI",
        "JWT_PUBLIC_KEY (or JWT_PUBLIC_KEY_PATH)": "JWT_PUBLIC_KEY",
        "MONSTER_SERVICE_URL": "MONSTER_SERVICE_URL",
        "INTERNAL_SERVICE_SECRET": "INTERNAL_SERVICE_SECRET",
    }
    missing = [name for name, key in required.items() if not settings[key]]
    if missing:
        raise StartupError("The Encounter Service cannot start. Missing settings: " + ", ".join(missing))
    return settings


MAX_BODY_BYTES = 10_000


def create_app(test_config=None, monster_client=None, draw=None):
    """Without `test_config`, the settings come from the environment.

    `draw` returns a random number in [0, 1). Production uses the operating
    system's secure generator, so nobody can predict a roll; tests pass a fixed die."""
    app = Flask(__name__)
    app.config.from_mapping(
        # Design rule 6: tokens are issued by the Player Service for this game.
        JWT_ISSUER="player-service",
        JWT_AUDIENCE="monster-tamers",
        # Lab 8: our biggest request is a few hundred bytes, so a bigger body is
        # refused with 413 before it is read.
        MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
    )
    app.config.update(_settings_from_environment() if test_config is None else test_config)

    if monster_client is None:  # production: the real Monster Service over HTTPS
        from .http_monster_client import HttpMonsterClient

        monster_client = HttpMonsterClient(
            app.config["MONSTER_SERVICE_URL"],
            app.config["INTERNAL_SERVICE_SECRET"],
            ca_cert_path=app.config.get("CA_CERT_PATH"),
        )
    app.extensions["monster_client"] = monster_client
    app.extensions["draw"] = draw or secrets.SystemRandom().random
    register_error_handlers(app)

    from .challenges import load_challenges

    db.init_app(app)
    with app.app_context():
        db.create_all()
        load_challenges()

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="encounter_service")

    from .challenges import challenges_bp
    from .encounters import encounters_bp
    from .team import team_bp

    app.register_blueprint(team_bp)
    app.register_blueprint(challenges_bp)
    app.register_blueprint(encounters_bp)

    return app
