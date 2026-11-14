"""Lab 8, data at rest: whoever copies encounter-db (a disk, a backup, a copy of
the volume) must not be able to read the monsters of an encounter, while the API
still answers with the clean data. What is stored is the behaviour under test
here, so these tests look inside the database on purpose."""

from sqlalchemy import text

from app.models import db

SPROUTPAW, DRIFIN, EMBERBUN, CINDRAKE = 1, 5, 9, 11  # catalogue IDs; challenge 11 is the wild Cindrake
TEAM = [SPROUTPAW, DRIFIN, EMBERBUN]


def _stored_snapshots(app, encounter_id):
    """The two snapshot columns exactly as the database holds them."""
    with app.app_context():
        row = db.session.execute(
            text("SELECT team_snapshot, wild_snapshot FROM encounter WHERE id = :id"), {"id": encounter_id}
        ).one()
    return " ".join(str(value) for value in row)


def test_the_monsters_of_an_encounter_are_stored_unreadable_and_returned_clean(app, game):
    team_ids = game.give_team("player-1", TEAM)
    opened = game.open("player-1", CINDRAKE).get_json()

    stored = _stored_snapshots(app, opened["id"])
    shown = game.show("player-1", opened["id"]).get_json()

    for plain in ["Sproutpaw", "Drifin", "Emberbun", "Cindrake", "grass", "water", "fire", *team_ids]:
        assert plain not in stored
    # The roster slide: Cindrake is a fire monster with ATK 7 and HP 6.
    assert shown["wild"] == {"species_id": CINDRAKE, "name": "Cindrake", "type": "fire", "atk": 7, "hp": 6}
    assert [monster["id"] for monster in shown["team"]] == team_ids
    assert shown["team"] == opened["team"]
