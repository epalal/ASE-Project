import os
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app import create_app
from app.models import db

# Genera una coppia di chiavi RSA 2048-bit temporanea per i test RS256
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode("utf-8")

PUBLIC_PEM = _private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode("utf-8")

INTERNAL_SECRET = "test-internal-secret-key"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_PUBLIC_KEY", PUBLIC_PEM)
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", INTERNAL_SECRET)

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.drop_all()

def make_token(player_id="player_test_1"):
    return jwt.encode({"sub": player_id}, PRIVATE_PEM, algorithm="RS256")

# --- TEST US-10: GET /monsters ---
def test_get_catalog_valid(client):
    """Test 2xx: The monster catalog returns exactly the 16 monsters with types Fire, Water, Darkness, Earth."""
    res = client.get("/monsters")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 16
    elements = {m["element"] for m in data}
    assert elements == {"Fire", "Water", "Darkness", "Earth"}

def test_get_catalog_invalid_method(client):
    """Test 4xx: Invalid method on the catalog."""
    res = client.post("/monsters", json={})
    assert res.status_code == 405

# --- TEST US-11: GET /monsters/<id> ---
def test_get_single_monster_valid(client):
    """Test 2xx: Request for a valid monster (ID 11 = Cindrake)."""
    res = client.get("/monsters/11")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "Cindrake"
    assert data["element"] == "Fire"
    assert data["power"] == 7
    assert data["hp"] == 6

def test_get_single_monster_invalid_id(client):
    """Test 4xx: Request for an invalid monster ID (outside the range 1-16) returns 404."""
    res = client.get("/monsters/99")
    assert res.status_code == 404
    assert "error" in res.get_json()

# --- TEST US-06 & US-09: GET /collection ---
def test_get_collection_lazy_init_valid(client):
    """Test 2xx: A new authenticated user gets the 4 starter monsters (Lazy Init)."""
    token = make_token("new_player_01")
    res = client.get("/collection", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["player_id"] == "new_player_01"
    assert data["count"] == 4
    starter_ids = [item["monster"]["id"] for item in data["collection"]]
    assert sorted(starter_ids) == [1, 5, 9, 15]

def test_get_collection_unauthorized_invalid(client):
    """Test 4xx: Request without a valid JWT token or with an invalid token returns 401."""
    res_no_token = client.get("/collection")
    assert res_no_token.status_code == 401

    res_bad_token = client.get("/collection", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res_bad_token.status_code == 401

# --- TEST US-12: POST /monsters/reward ---
def test_grant_reward_valid_and_idempotent(client):
    """Test 2xx: Grant a reward for a valid monster and ensure idempotency."""
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    payload = {
        "player_id": "player_winner",
        "monster_id": 7,  # Dolwhale
        "encounter_id": "enc_001"
    }
    # First call -> 201 Created
    res1 = client.post("/monsters/reward", json=payload, headers=headers)
    assert res1.status_code == 201
    assert res1.get_json()["reward"]["monster"]["name"] == "Dolwhale"

    # Second call with the same encounter_id -> 200 OK (no duplicate added)
    res2 = client.post("/monsters/reward", json=payload, headers=headers)
    assert res2.status_code == 200

    # Verify that the player's collection now has 5 monsters (4 starters + 1 reward)
    token = make_token("player_winner")
    col_res = client.get("/collection", headers={"Authorization": f"Bearer {token}"})
    assert col_res.get_json()["count"] == 5

def test_grant_reward_invalid_inputs(client):
    """Test 4xx: Call without internal secret (403), payload incomplete (400) or non-existent monster (404)."""
    # 1. Senza header X-Internal-Secret -> 403 Forbidden
    res_forbidden = client.post("/monsters/reward", json={"player_id": "p1", "monster_id": 1, "encounter_id": "e1"})
    assert res_forbidden.status_code == 403

    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    # 2. Payload privo di encounter_id -> 400 Bad Request
    res_bad_req = client.post("/monsters/reward", json={"player_id": "p1", "monster_id": 1}, headers=headers)
    assert res_bad_req.status_code == 400

    # 3. monster_id inesistente -> 404 Not Found
    res_not_found = client.post("/monsters/reward", json={"player_id": "p1", "monster_id": 999, "encounter_id": "e2"}, headers=headers)
    assert res_not_found.status_code == 404