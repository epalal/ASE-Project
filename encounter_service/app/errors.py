from flask import jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .models import db
from .monster_client import MonsterServiceTimeout, MonsterServiceUnavailable


def error(code, message, status):
    """Every error has the same shape, as agreed in issue #21."""
    return jsonify(error=code, message=message), status


def register_error_handlers(app):
    """Every error leaves the service in the same JSON shape.

    A failing Monster Service is reported as in Lab 6: 504 when it is too slow,
    502 when it is down or answers with an error."""

    @app.errorhandler(HTTPException)
    def http_error(failure):  # 404, 405, and the 500 that Flask makes from a crash
        return error(failure.name.lower().replace(" ", "_"), failure.description, failure.code)

    @app.errorhandler(IntegrityError)
    def conflict(_):  # two requests wrote the same rows at the same instant
        db.session.rollback()
        return error("conflict", "Another request changed the same data at the same moment. Try again.", 409)

    @app.errorhandler(MonsterServiceTimeout)
    def monster_service_timeout(_):
        return error("monster_service_timeout", "The Monster Service did not answer in time.", 504)

    @app.errorhandler(MonsterServiceUnavailable)
    def monster_service_unavailable(_):
        return error("monster_service_unavailable", "The Monster Service cannot be reached right now.", 502)
