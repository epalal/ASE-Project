"""Challenge list (US-17), tested through the HTTP API."""

from app import create_app

# The 16 monsters of the roster slide, with the IDs of Elena's catalogue.
ROSTER = {
    1: "Sproutpaw", 2: "Vineclaw", 3: "Bramblebane", 4: "Mossbear",
    5: "Drifin", 6: "Tideglider", 7: "Dolwhale", 8: "Frosthart",
    9: "Emberbun", 10: "Blazetiger", 11: "Cindrake", 12: "Ashwing",
    13: "Duskpaka", 14: "Colt", 15: "Budbug", 16: "Leaflark",
}  # fmt: skip


def test_a_player_sees_one_challenge_for_each_of_the_16_monsters(client, token_for):
    response = client.get("/challenges", headers=token_for("player-1"))

    challenges = response.get_json()["challenges"]
    assert response.status_code == 200
    assert {c["wild_species_id"]: c["name"] for c in challenges} == {
        species_id: f"Wild {name}" for species_id, name in ROSTER.items()
    }
    assert all(c["description"] for c in challenges)


def test_restarting_the_service_does_not_load_the_challenges_twice(
    tmp_path, player_service_keys, monster_service, token_for
):
    _, public_pem = player_service_keys
    same_database = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'encounter.db'}",
        "JWT_PUBLIC_KEY": public_pem,
    }
    create_app(same_database, monster_client=monster_service)  # first start
    restarted = create_app(same_database, monster_client=monster_service)

    response = restarted.test_client().get("/challenges", headers=token_for("player-1"))

    assert len(response.get_json()["challenges"]) == 16


def test_the_challenge_list_needs_a_login_token(client):
    response = client.get("/challenges")

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
