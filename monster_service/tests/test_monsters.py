import os
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app import create_app
from app.models import db

# Generate a temporary RS256 key pair for testing JWTs
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

# Set environment variables for the test
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

# Generate a JWT token for a given player ID
def make_token(player_id="player_test_1"):
    return jwt.encode({"sub": player_id}, PRIVATE_PEM, algorithm="RS256")

# TEST US-10: "browse all existing monsters available" GET /monsters 
def test_get_catalog_valid(client):
    """Test 2xx: The monster catalog returns exactly the 16 monsters with types Fire, Water, Dark, Grass."""
    res = client.get("/monsters")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 16
    elements = {m["element"] for m in data}
    assert elements == {"Fire", "Water", "Dark", "Grass"}

# TEST US-10: Invalid method on the catalog
def test_get_catalog_invalid_method(client):
    """Test 4xx: Invalid method on the catalog."""
    res = client.post("/monsters", json={})
    assert res.status_code == 405

# TEST US-11: "view a monster's image and details" GET /monsters/<id>
def test_get_single_monster_valid(client):
    """Test 2xx: Request for a valid monster (ID 11 = Cindrake)."""
    res = client.get("/monsters/11")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "Cindrake"
    assert data["element"] == "Fire"
    assert data["power"] == 7
    assert data["hp"] == 6

# TEST US-11: Invalid monster ID (outside the range 1-16)
def test_get_single_monster_invalid_id(client):
    """Test 4xx: Request for an invalid monster ID (outside the range 1-16) returns 404."""
    res = client.get("/monsters/99")
    assert res.status_code == 404
    assert "error" in res.get_json()

# TEST US-06 & US-09: "recieve an initial set of monsters when I start palying" and "view monster I own" GET /collection
def test_get_collection_lazy_init_valid(client):
    """Test 2xx: A new authenticated user gets the 3 starter monsters (Lazy Init)."""
    token = make_token("new_player_01")
    res = client.get("/collection", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["player_id"] == "new_player_01"
    assert data["count"] == 3
    starter_ids = [item["monster"]["id"] for item in data["collection"]]
    assert sorted(starter_ids) == [1, 5, 9]

# TEST US-06 & US-09: Invalid JWT token
def test_get_collection_unauthorized_invalid(client):
    """Test 4xx: Request without a valid JWT token or with an invalid token returns 401."""
    res_no_token = client.get("/collection")
    assert res_no_token.status_code == 401

    res_bad_token = client.get("/collection", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res_bad_token.status_code == 401

# TEST C10: Capture reward from the Encounter service
def test_grant_reward_valid_and_idempotent(client):
    """Test 2xx: Grant a reward for a valid monster and ensure idempotency."""
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    payload = {
        "player_id": "player_winner",
        "captured_species_id": 7,  # Dolwhale
        "encounter_id": "enc_001"
    }
    # First call -> 201 Created
    res1 = client.post("/internal/rewards", json=payload, headers=headers)
    assert res1.status_code == 201
    assert res1.get_json()["reward"]["monster"]["name"] == "Dolwhale"

    # Second call with the same encounter_id -> 200 OK (no duplicate added)
    res2 = client.post("/internal/rewards", json=payload, headers=headers)
    assert res2.status_code == 200

    # Verify that the player's collection now has 5 monsters (3 starters + 1 reward)
    token = make_token("player_winner")
    col_res = client.get("/collection", headers={"Authorization": f"Bearer {token}"})
    assert col_res.get_json()["count"] == 4

# TEST C10: Invalid inputs for granting a reward
def test_grant_reward_invalid_inputs(client):
    """Test 4xx: Call without internal secret (403), payload incomplete (400) or non-existent monster (404)."""
    # 1. No header X-Internal-Secret -> 403 Forbidden
    res_forbidden = client.post("/internal/rewards", json={"player_id": "p1", "captured_species_id": 1, "encounter_id": "e1"})
    assert res_forbidden.status_code == 403

    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    # 2. Payload without encounter_id -> 400 Bad Request
    res_bad_req = client.post("/internal/rewards", json={"player_id": "p1", "captured_species_id": 1}, headers=headers)
    assert res_bad_req.status_code == 400

    # 3. monster_id not found -> 404 Not Found
    res_not_found = client.post("/internal/rewards", json={"player_id": "p1", "captured_species_id": 999, "encounter_id": "e2"}, headers=headers)
    assert res_not_found.status_code == 404

# TEST C10: Stats reward applies capped bonuses
def test_stats_reward_applies_capped_bonuses(client):
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    token = make_token("player_stats")
    collection = client.get("/collection", headers={"Authorization": f"Bearer {token}"}).get_json()["collection"]
    owned_id = collection[0]["ownership_id"]

    res = client.post(
        "/internal/rewards",
        json={
            "player_id": "player_stats",
            "owned_monster_ids": [owned_id],
            "atk_bonus": 99,
            "hp_bonus": 99,
            "encounter_id": "enc_stats",
        },
        headers=headers,
    )
    assert res.status_code == 200
    updated = res.get_json()["updated_monsters"][0]
    assert updated["atk"] == updated["monster"]["power"] + 3
    assert updated["hp"] == updated["monster"]["hp"] + 3

# TEST C10: Team snapshot returns owned species IDs
def test_team_snapshot_returns_owned_species_ids(client):
    headers = {"X-Internal-Secret": INTERNAL_SECRET}
    res = client.get("/internal/players/player_team/team", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["owned_species_ids"] == [1, 5, 9]
