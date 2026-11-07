from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import error


def require_player(view):
    """The player's identity comes only from the login token (design rule 2).
    The token is signed by the Player Service; we check it with its public key."""

    @wraps(view)
    def guarded(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("unauthorized", "A valid login token is required.", 401)
        try:
            claims = jwt.decode(
                header.removeprefix("Bearer "),
                current_app.config["JWT_PUBLIC_KEY"],
                algorithms=["RS256"],
                audience=current_app.config["JWT_AUDIENCE"],
                issuer=current_app.config["JWT_ISSUER"],
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.InvalidTokenError:  # forged, expired, malformed, wrong audience/issuer, or missing a claim
            return error("unauthorized", "A valid login token is required.", 401)
        g.player_id = claims["sub"]
        return view(*args, **kwargs)

    return guarded
