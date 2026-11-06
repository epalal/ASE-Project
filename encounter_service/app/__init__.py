import os

from flask import Flask, jsonify

from .models import db


def create_app(test_config=None, monster_client=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        JWT_PUBLIC_KEY=os.environ.get("JWT_PUBLIC_KEY", "").replace("\\n", "\n"),
    )
    if test_config:
        app.config.update(test_config)

    app.extensions["monster_client"] = monster_client

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
