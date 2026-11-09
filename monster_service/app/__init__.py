import os
from flask import Flask, send_from_directory, jsonify
from .models import db
from .routes.monsters import monsters_bp

def create_app(test_config=None):
    app = Flask(__name__)
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@monster_db:5432/monster_db")
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=db_url,
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
        db.create_all()
        from .initial_monsters import init_catalog
        init_catalog()

    return app