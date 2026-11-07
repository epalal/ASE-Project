"""Starting the service for real: its settings come from environment variables
(set by Docker Compose), and a missing setting stops the start with a clear message."""

import pytest

from app import StartupError, create_app
from conftest import STUB_SECRET

ALL_SETTINGS = [
    "DATABASE_URL",
    "JWT_PUBLIC_KEY",
    "JWT_PUBLIC_KEY_PATH",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "MONSTER_SERVICE_URL",
    "INTERNAL_SERVICE_SECRET",
    "CA_CERT_PATH",
]


@pytest.fixture
def empty_environment(monkeypatch):
    for name in ALL_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def test_the_service_refuses_to_start_without_its_settings(empty_environment):
    with pytest.raises(StartupError) as refused:
        create_app()

    for missing in ["DATABASE_URL", "JWT_PUBLIC_KEY", "MONSTER_SERVICE_URL", "INTERNAL_SERVICE_SECRET"]:
        assert missing in str(refused.value)


def test_with_its_settings_it_talks_to_the_monster_service_over_http(
    empty_environment, monkeypatch, tmp_path, stub_url, player_service_keys, token_for
):
    _, public_pem = player_service_keys
    key_file = tmp_path / "jwt_public.pem"
    key_file.write_text(public_pem)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'encounter.db'}")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(key_file))
    monkeypatch.setenv("MONSTER_SERVICE_URL", stub_url)
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", STUB_SECRET)
    client = create_app().test_client()

    # 101, 105 and 109 are starters the Monster Service stub gives every player.
    saved = client.put("/team", json={"monster_ids": ["101", "105", "109"]}, headers=token_for("player-1"))
    team = client.get("/team", headers=token_for("player-1"))

    assert saved.status_code == 200
    assert team.get_json() == {"monster_ids": ["101", "105", "109"]}
