import sys
from pathlib import Path
import jwt
import pytest
from bcrypt import hashpw, gensalt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Isolates the path of player_service to avoid collisions with other microservices
SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

import app as app_module
from db.db import SessionLocal, User, engine


@pytest.fixture(scope="session")
def rsa_key_pair(tmp_path_factory):
    """Generates a pair of RSA keys once for the whole test session."""
    certs_dir = tmp_path_factory.mktemp("certs")
    private_path = certs_dir / "jwt_private.pem"
    public_path = certs_dir / "jwt_public.pem"

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pem_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    private_path.write_text(pem_private)
    public_path.write_text(pem_public)

    return {
        "private_path": str(private_path),
        "public_path": str(public_path),
        "public_pem": pem_public,
    }


@pytest.fixture
def client(monkeypatch, rsa_key_pair):
    """Configures the Flask client redirecting the paths of JWT keys."""
    monkeypatch.setattr(app_module, "PRIVATE_KEY_PATH", rsa_key_pair["private_path"])
    monkeypatch.setattr(app_module, "PUBLIC_KEY_PATH", rsa_key_pair["public_path"])

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture
def db_session():
    """Initializes a test user before each test and cleans everything at the end."""
    engine.echo = False
    session = SessionLocal()
    try:
        session.query(User).delete()
        session.commit()

        hashed_password = hashpw("testpassword".encode("utf-8"), gensalt()).decode("utf-8")
        test_user = User(username="testuser", password_hashed=hashed_password)
        session.add(test_user)
        session.commit()
        session.refresh(test_user)

        yield session, test_user
    finally:
        session.rollback()
        session.query(User).delete()
        session.commit()
        session.close()

# Heath test
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}

# Account test
def test_account_creation_success(client, db_session):
    session, _ = db_session
    response = client.post("/account", json={
        "username": "newuser",
        "password": "newpassword",
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    assert response.get_json() == {"message": "Account created successfully"}

    session.expire_all()
    user = session.query(User).filter_by(username="newuser").first()
    assert user is not None
    assert user.username == "newuser"

def test_account_creation_existing_user(client, db_session):
    response = client.post("/account", json={
        "username": "testuser",
        "password": "anotherpassword",
    })
    assert response.status_code == 409
    assert response.get_json() == {"error": "user_exists", "message": "Username already exists"}

@pytest.mark.parametrize("payload,expected_error", [
    ({"username": 123, "password": "valid"}, "invalid_input"),
    ({"username": "valid"}, "invalid_input"),
    (["not", "a", "dict"], "invalid_request"),
])
def test_account_creation_bad_payloads(client, db_session, payload, expected_error):
    response = client.post("/account", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error

# Login test
def test_login_success(client, db_session, rsa_key_pair):
    _, test_user = db_session
    response = client.post("/login", json={
        "username": "testuser",
        "password": "testpassword",
    })
    assert response.status_code == 200, response.get_data(as_text=True)

    data = response.get_json()
    assert data["message"] == "Successful login"
    assert data["username"] == "testuser"
    assert data["id"] == test_user.id
    assert "token" in data

    decoded = jwt.decode(
        data["token"],
        rsa_key_pair["public_pem"],
        algorithms=["RS256"],
    )
    assert decoded["iss"] == "player-service"
    assert decoded["sub"] == str(test_user.id)
    assert decoded["username"] == "testuser"

def test_login_invalid_credentials(client, db_session):
    response = client.post("/login", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized", "message": "Invalid username or password"}

def test_login_missing_keys_returns_500(monkeypatch, db_session):
    """Verifies the behaviour when JWT key files don't exist."""
    monkeypatch.setattr(app_module, "PRIVATE_KEY_PATH", "/nonexistent/path/private.pem")
    monkeypatch.setattr(app_module, "PUBLIC_KEY_PATH", "/nonexistent/path/public.pem")

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        response = client.post("/login", json={
            "username": "testuser",
            "password": "testpassword",
        })
    assert response.status_code == 500
    assert response.get_json() == {"error": "server_error", "message": "JWT signing keys not available"}