"""Design rule 7: services talk over HTTPS with certificates from our own
certificate authority, made by tls_init/make_certs.py, and refuse any other."""

import stat

import jwt
import pytest

from app.http_monster_client import HttpMonsterClient
from app.monster_client import MonsterServiceUnavailable, Species
from conftest import STUB_SECRET, run_in_background
from make_certs import make_certs
from stub import create_stub


@pytest.fixture
def tls(tmp_path):
    """Our certificate authority and the certificates of three services."""
    out = tmp_path / "tls"
    make_certs(out, services=["monster-service", "encounter-service", "player-service"])
    return out


@pytest.fixture
def https_stub(tls):
    """The Monster Service stub over HTTPS, with the monster-service certificate."""
    certificate = tls / "monster-service"
    server = run_in_background(
        create_stub(internal_secret=STUB_SECRET),
        ssl_context=(str(certificate / "server.pem"), str(certificate / "server.key")),
    )
    yield f"https://localhost:{server.server_port}"
    server.shutdown()


def test_a_service_certificate_from_our_authority_is_trusted(tls, https_stub):
    # The Encounter Service trusts our authority through the ca.pem in its own folder.
    monster_service = HttpMonsterClient(
        https_stub, STUB_SECRET, ca_cert_path=str(tls / "encounter-service" / "ca.pem")
    )

    assert monster_service.get_species(9) == Species(id=9, name="Emberbun", type="fire", atk=3, hp=2)


def test_a_server_with_a_certificate_from_another_authority_is_refused(tmp_path, tls):
    # Someone inside the network pretends to be the Monster Service, with a
    # certificate that our authority did not sign.
    impostor = tmp_path / "impostor"
    make_certs(impostor, services=["monster-service"])
    certificate = impostor / "monster-service"
    server = run_in_background(
        create_stub(internal_secret=STUB_SECRET),
        ssl_context=(str(certificate / "server.pem"), str(certificate / "server.key")),
    )
    monster_service = HttpMonsterClient(
        f"https://localhost:{server.server_port}",
        STUB_SECRET,
        ca_cert_path=str(tls / "encounter-service" / "ca.pem"),
    )

    try:
        with pytest.raises(MonsterServiceUnavailable):
            monster_service.get_species(9)
    finally:
        server.shutdown()


# Design rule 6: only the Player Service can create login tokens.
def test_only_the_player_service_gets_the_key_that_signs_login_tokens(tls):
    assert (tls / "player-service" / "jwt_private.pem").exists()
    assert not (tls / "encounter-service" / "jwt_private.pem").exists()
    assert not (tls / "monster-service" / "jwt_private.pem").exists()


def test_starting_again_keeps_the_authority_and_the_token_keys(tls):
    # tls-init runs at every `docker compose up`; tokens and certificates issued
    # before a restart must stay valid after it.
    authority_before = (tls / "ca" / "ca.pem").read_bytes()
    token_key_before = (tls / "player-service" / "jwt_private.pem").read_bytes()

    make_certs(tls, services=["monster-service", "encounter-service", "player-service"])

    assert (tls / "ca" / "ca.pem").read_bytes() == authority_before
    assert (tls / "player-service" / "jwt_private.pem").read_bytes() == token_key_before


def _permissions(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_private_keys_can_be_read_only_by_their_owner_and_the_certificate_group(tls):
    # Every service runs as its own non-root user and reads its key through the
    # certificate group, which it joins in Docker Compose. The authority's keys
    # stay with tls-init alone.
    assert _permissions(tls / "encounter-service" / "server.key") == 0o640
    assert _permissions(tls / "player-service" / "jwt_private.pem") == 0o640
    assert _permissions(tls / "ca" / "ca.key") == 0o600
    assert _permissions(tls / "ca" / "jwt_private.pem") == 0o600


def test_a_token_signed_by_the_player_service_is_accepted_by_the_other_services(tls):
    signing_key = (tls / "player-service" / "jwt_private.pem").read_bytes()
    checking_key = (tls / "encounter-service" / "jwt_public.pem").read_text()

    token = jwt.encode({"sub": "player-1"}, signing_key, algorithm="RS256")

    assert jwt.decode(token, checking_key, algorithms=["RS256"])["sub"] == "player-1"
