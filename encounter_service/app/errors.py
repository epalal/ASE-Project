from flask import jsonify


def error(code, message, status):
    """Every error has the same shape, as agreed in issue #21."""
    return jsonify(error=code, message=message), status
