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


class Challenge(db.Model):
    """One wild monster a player can face. Its stats stay in the Monster
    Service's catalogue; this table only says which species it is."""

    __tablename__ = "challenge"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    wild_species_id = db.Column(db.Integer, nullable=False, unique=True)


class Encounter(db.Model):
    """One encounter. The snapshots keep the stats used at the time, so the
    history stays right after rewards change the monsters."""

    __tablename__ = "encounter"

    id = db.Column(db.String(36), primary_key=True)  # UUID
    player_id = db.Column(db.String(64), nullable=False, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenge.id"), nullable=False)
    status = db.Column(db.String(8), nullable=False)
    team_snapshot = db.Column(db.JSON, nullable=False)
    wild_snapshot = db.Column(db.JSON, nullable=False)
    team_power = db.Column(db.Float, nullable=False)
    challenge_power = db.Column(db.Float, nullable=False)
    p_win = db.Column(db.Float, nullable=False)
    p_capture = db.Column(db.Float, nullable=True)  # empty when capture is not offered
    action = db.Column(db.String(8), nullable=True)  # attack, capture or escape; empty while open
    roll = db.Column(db.Float, nullable=True)  # empty while open and for an escape
    result = db.Column(db.String(8), nullable=True)  # win, loss, captured, failed or escaped
    reward_status = db.Column(db.String(8), nullable=False, default="none")  # none, pending, applied, failed
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint("status IN ('open', 'closed')", name="encounter_status"),
        # The database itself allows only one open encounter per player.
        db.Index(
            "one_open_encounter_per_player",
            "player_id",
            unique=True,
            sqlite_where=db.text("status = 'open'"),
            postgresql_where=db.text("status = 'open'"),
        ),
    )
