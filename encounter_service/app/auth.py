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
            # RFC 6750, section 3: say that this API expects a Bearer token.
            response, status = error("unauthorized", "A valid login token is required.", 401)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response, status
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
            # RFC 6750, section 3.1: a token was sent, but it is not valid.
            response, status = error("unauthorized", "A valid login token is required.", 401)
            response.headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
            return response, status
        player_id = claims.get("sub")
        if (
            not isinstance(player_id, str)
            or not 0 < len(player_id.strip()) <= 64
            or not player_id.strip().isprintable()
        ):
            response, status = error("unauthorized", "A valid login token is required.", 401)
            response.headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
            return response, status
        g.player_id = player_id.strip()
        return view(*args, **kwargs)

    return guarded
