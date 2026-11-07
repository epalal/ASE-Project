"""Challenge list: GET /challenges (US-17)."""

from flask import Blueprint, jsonify

from .auth import require_player
from .models import Challenge, db

challenges_bp = Blueprint("challenges", __name__)

# One challenge per monster. The IDs must match the Monster Service's
# catalogue (Elena's initial_monsters.py), because a challenge only stores
# the species ID and reads the stats from that catalogue.
CATALOGUE = [
    (1, "Sproutpaw"), (2, "Vineclaw"), (3, "Bramblebane"), (4, "Mossbear"),
    (5, "Drifin"), (6, "Tideglider"), (7, "Dolwhale"), (8, "Frosthart"),
    (9, "Emberbun"), (10, "Blazetiger"), (11, "Cindrake"), (12, "Ashwing"),
    (13, "Duskpaka"), (14, "Colt"), (15, "Budbug"), (16, "Leaflark"),
]  # fmt: skip


def load_challenges():
    """Fill the challenge table on the first start only."""
    if Challenge.query.first() is not None:
        return
    for species_id, name in CATALOGUE:
        db.session.add(
            Challenge(
                id=species_id,
                name=f"Wild {name}",
                description=f"A wild {name} appears. Attack it, try to capture it or escape.",
                wild_species_id=species_id,
            )
        )
    db.session.commit()


@challenges_bp.get("/challenges")
@require_player
def list_challenges():
    challenges = Challenge.query.order_by(Challenge.id).all()
    return jsonify(
        challenges=[
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "wild_species_id": c.wild_species_id,
            }
            for c in challenges
        ]
    )
