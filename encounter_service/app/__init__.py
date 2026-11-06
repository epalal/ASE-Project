import os
import secrets

from flask import Flask, jsonify

from .errors import register_error_handlers
from .models import db


def create_app(test_config=None, monster_client=None, draw=None):
    """`draw` returns a random number in [0, 1). Production uses the operating
    system's secure generator, so nobody can predict a roll; tests pass a fixed die."""
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
        # Design rule 6: tokens are issued by the Player Service for this game.
        JWT_ISSUER=os.environ.get("JWT_ISSUER", "player-service"),
        JWT_AUDIENCE=os.environ.get("JWT_AUDIENCE", "monster-tamers"),
    )
    if test_config:
        app.config.update(test_config)

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
