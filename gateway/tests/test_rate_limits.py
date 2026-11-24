import os

os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

from gateway.app import create_app


def test_monster_catalog_is_limited_per_ip(monkeypatch):
    app = create_app({"TESTING": True, "RATELIMIT_STORAGE_URI": "memory://"})
    monkeypatch.setattr("gateway.app.forward", lambda *args, **kwargs: ([], None))
    client = app.test_client()

    for _ in range(30):
        assert client.get("/monsters").status_code == 200

    response = client.get("/monsters")
    assert response.status_code == 429
    assert response.get_json()["error"] == "rate_limit_exceeded"
    assert client.get(
        "/monsters",
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    ).status_code == 200


def test_collection_limit_is_separate_from_catalog_limit(monkeypatch):
    app = create_app({"TESTING": True, "RATELIMIT_STORAGE_URI": "memory://"})
    monkeypatch.setattr("gateway.app.forward", lambda *args, **kwargs: ({}, None))
    client = app.test_client()

    for _ in range(30):
        assert client.get("/monsters").status_code == 200
    for _ in range(30):
        assert client.get("/collection").status_code == 200

    response = client.get("/collection")
    assert response.status_code == 429
