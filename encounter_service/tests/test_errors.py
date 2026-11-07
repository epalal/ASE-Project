"""Every error answers with {"error": code, "message": text} (issue #21)."""

from sqlalchemy.exc import IntegrityError


def test_an_unknown_address_answers_in_json(client):
    response = client.get("/nowhere")

    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_a_wrong_method_answers_in_json(client, token_for):
    response = client.delete("/team", headers=token_for("player-1"))

    assert response.status_code == 405
    assert response.get_json()["error"] == "method_not_allowed"


def test_two_writes_that_clash_answer_409_in_json(app):
    # Two requests that write the same rows at the same instant make the database
    # refuse one of them. That cannot be timed through the real endpoints, so this
    # route raises the same database error directly.
    @app.get("/test-only/clash")
    def clash():
        raise IntegrityError("INSERT INTO encounter ...", {}, Exception("UNIQUE constraint failed"))

    response = app.test_client().get("/test-only/clash")

    assert response.status_code == 409
    assert response.get_json()["error"] == "conflict"
