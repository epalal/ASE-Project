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


def test_gateway_rejects_nan_oversized_and_path_traversal(monkeypatch):
    app = create_app({"TESTING": True, "RATELIMIT_STORAGE_URI": "memory://"})
    client = app.test_client()

    res_nan = client.post(
        "/encounters",
        data='{"challenge_id": NaN}',
        content_type="application/json",
    )
    assert res_nan.status_code == 400
    assert res_nan.get_json()["error"] == "invalid_request"

    res_traversal = client.get("/encounters/..%2Fteam")
    assert res_traversal.status_code in (400, 404)
    assert "error" in res_traversal.get_json()

    res_dotdot = client.get("/encounters/..")
    assert res_dotdot.status_code == 400
    assert res_dotdot.get_json()["error"] == "invalid_request"

    res_asset_traversal = client.get("/assets/monsters/..%2Fsecret.txt")
    assert res_asset_traversal.status_code in (400, 404)

    res_asset_dotdot = client.get("/assets/monsters/..")
    assert res_asset_dotdot.status_code == 400

    huge = '{"username": "' + "a" * 11_000 + '", "password": "securepassword"}'
    res_large = client.post("/account", data=huge, content_type="application/json")
    assert res_large.status_code == 413
    assert res_large.get_json()["error"] == "request_entity_too_large"

    not_found = client.get("/internal/rewards")
    assert not_found.status_code == 404
    assert "error" in not_found.get_json()
    assert "message" in not_found.get_json()


def test_gateway_proxies_monster_assets(monkeypatch):
    class FakeAssetResponse:
        status_code = 200
        content = b"fake-jpeg-bytes"
        headers = {"Content-Type": "image/jpeg"}

    app = create_app({"TESTING": True, "RATELIMIT_STORAGE_URI": "memory://"})
    monkeypatch.setattr("gateway.app.requests.get", lambda *args, **kwargs: FakeAssetResponse())
    client = app.test_client()

    res = client.get("/assets/monsters/Monster%20collection_1.jpeg")
    assert res.status_code == 200
    assert res.data == b"fake-jpeg-bytes"
    assert res.mimetype == "image/jpeg"
