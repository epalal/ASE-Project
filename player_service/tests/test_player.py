import json
import logging
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app


@pytest.fixture(scope="session")
def rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def client(rsa_key_pair):
    private_pem, _ = rsa_key_pair
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_PRIVATE_KEY": private_pem,
        }
    )
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "healthy"}


def test_account_creation_uses_uuid_and_prevents_duplicates(client):
    res = client.post("/account", json={"username": "tamer_alice", "password": "securepassword"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["username"] == "tamer_alice"
    parsed = uuid.UUID(body["id"])
    assert str(parsed) == body["id"]

    dup = client.post("/account", json={"username": "tamer_alice", "password": "securepassword"})
    assert dup.status_code == 409
    assert dup.get_json()["error"] == "user_exists"


def test_login_issues_valid_rs256_jwt(client, rsa_key_pair):
    _, public_pem = rsa_key_pair
    created = client.post("/account", json={"username": "tamer_bob", "password": "securepassword"}).get_json()

    res = client.post("/login", json={"username": "tamer_bob", "password": "securepassword"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["id"] == created["id"]
    assert data["username"] == "tamer_bob"

    claims = jwt.decode(
        data["token"],
        public_pem,
        algorithms=["RS256"],
        issuer="player-service",
        audience="monster-tamers",
        options={"require": ["exp", "iat", "iss", "sub", "aud"]},
    )
    assert claims["sub"] == created["id"]
    assert claims["username"] == "tamer_bob"


def test_login_rejects_wrong_credentials(client):
    client.post("/account", json={"username": "tamer_bob", "password": "securepassword"})
    res = client.post("/login", json={"username": "tamer_bob", "password": "wrongpassword"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "unauthorized"


@pytest.mark.parametrize(
    "raw_body",
    [
        '{"username": "u1", "password": NaN}',
        '{"username": "u1", "password": 1e999}',
        "not-json",
        "[]",
        '{"username": "bad user", "password": "securepassword"}',
        '{"username": "u1\\u0000", "password": "securepassword"}',
        '{"username": "u1\\n", "password": "securepassword"}',
        '{"username": "u1", "password": "abc"}',
        json.dumps({"username": "u1", "password": "p" * 73}),
        json.dumps({"username": "u" * 65, "password": "securepassword"}),
    ],
)
def test_hostile_and_invalid_inputs_are_refused(client, raw_body):
    res = client.post("/account", data=raw_body, content_type="application/json")
    assert res.status_code == 400
    assert res.get_json()["error"] == "invalid_input"


def test_oversized_body_returns_413_json(client):
    huge = '{"username": "' + "a" * 11_000 + '", "password": "securepassword"}'
    res = client.post("/account", data=huge, content_type="application/json")
    assert res.status_code == 413
    assert res.get_json()["error"] == "request_entity_too_large"


def test_errors_always_return_json(client):
    not_found = client.get("/missing")
    assert not_found.status_code == 404
    assert "error" in not_found.get_json()
    assert "message" in not_found.get_json()

    bad_method = client.delete("/login")
    assert bad_method.status_code == 405
    assert bad_method.get_json()["error"] == "method_not_allowed"


def test_audit_log_never_leaks_passwords_or_tokens(client, caplog):
    caplog.set_level(logging.INFO, logger="audit")
    secret_pw = "MySuperSecretPw123"
    client.post("/account", json={"username": "audit_user", "password": secret_pw})
    login_res = client.post("/login", json={"username": "audit_user", "password": secret_pw})
    token = login_res.get_json()["token"]

    assert secret_pw not in caplog.text
    assert token not in caplog.text
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "audit"]
    assert len(records) == 2
    assert records[0]["outcome"] == "success"
    assert records[1]["outcome"] == "success"
