"""encounter-db tables (docs/architecture.md, "encounter-db")."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class TeamMember(db.Model):
    """One of the three team slots. Player and monster IDs come from other
    services, so they are plain text, not foreign keys."""

    __tablename__ = "team_member"

    player_id = db.Column(db.String(64), primary_key=True)
    slot = db.Column(db.Integer, primary_key=True)
    owned_monster_id = db.Column(db.String(64), nullable=False)

    __table_args__ = (
        db.CheckConstraint("slot BETWEEN 1 AND 3", name="team_slot_range"),
        db.UniqueConstraint("player_id", "owned_monster_id", name="team_no_duplicate_monster"),
    )
