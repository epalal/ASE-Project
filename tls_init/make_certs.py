"""Makes the HTTPS certificates of every service (design rule 7).

It runs as a one-shot container (tls-init) before the other services start in
Docker Compose, so `docker compose up` alone still builds and starts everything.
Each folder below OUT is one Docker volume, mounted only by the service it belongs to:

  ca/                  our certificate authority and the login-token key pair
                       (only tls-init mounts this one)
  <service>/ca.pem     the authority's certificate, to trust the other services
  <service>/server.pem, server.key
                       this service's certificate, valid for its Docker name and localhost
  <service>/jwt_public.pem
                       the key that checks login tokens (design rule 6)
  player-service/jwt_private.pem
                       the key that signs login tokens: only the Player Service gets it
"""

import datetime as dt
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

SERVICES = [
    "gateway",
    "player-service",
    "monster-service",
    "encounter-service",
    "player-db",
    "monster-db",
    "encounter-db",
]
TOKEN_SIGNER = "player-service"  # the only service that may create login tokens
VALID_DAYS = 365


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _write_key(path, key):
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )


def _write_certificate(path, certificate):
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def _validity(builder):
    now = dt.datetime.now(dt.timezone.utc)
    return builder.not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=VALID_DAYS))


def _make_authority(folder):
    key = _new_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Monster Tamers development CA")])
    certificate = (
        _validity(x509.CertificateBuilder())
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_key(folder / "ca.key", key)
    _write_certificate(folder / "ca.pem", certificate)
    return key, certificate


def _make_service_certificate(service, authority_key, authority_certificate):
    key = _new_key()
    certificate = (
        _validity(x509.CertificateBuilder())
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, service)]))
        .issuer_name(authority_certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName(service),
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(authority_key.public_key()), critical=False
        )
        .sign(authority_key, hashes.SHA256())
    )
    return key, certificate


def _make_token_keys(folder):
    key = _new_key()
    _write_key(folder / "jwt_private.pem", key)
    (folder / "jwt_public.pem").write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


def _load_authority(folder):
    key = serialization.load_pem_private_key((folder / "ca.key").read_bytes(), password=None)
    certificate = x509.load_pem_x509_certificate((folder / "ca.pem").read_bytes())
    return key, certificate


def _all_exist(*paths):
    return all(path.exists() for path in paths)


def make_certs(out, services=SERVICES):
    """Runs at every `docker compose up`: what already exists is kept, so the
    certificates and login tokens issued before a restart stay valid."""
    out = Path(out)
    authority_folder = out / "ca"
    authority_folder.mkdir(parents=True, exist_ok=True)
    if _all_exist(authority_folder / "ca.key", authority_folder / "ca.pem"):
        authority_key, authority_certificate = _load_authority(authority_folder)
    else:
        authority_key, authority_certificate = _make_authority(authority_folder)
    if not _all_exist(authority_folder / "jwt_private.pem", authority_folder / "jwt_public.pem"):
        _make_token_keys(authority_folder)

    for service in services:
        folder = out / service
        folder.mkdir(exist_ok=True)
        _write_certificate(folder / "ca.pem", authority_certificate)
        if not _all_exist(folder / "server.key", folder / "server.pem"):
            key, certificate = _make_service_certificate(service, authority_key, authority_certificate)
            _write_key(folder / "server.key", key)
            _write_certificate(folder / "server.pem", certificate)
        (folder / "jwt_public.pem").write_bytes((authority_folder / "jwt_public.pem").read_bytes())
        if service == TOKEN_SIGNER:
            (folder / "jwt_private.pem").write_bytes((authority_folder / "jwt_private.pem").read_bytes())


if __name__ == "__main__":
    make_certs(
        os.environ.get("TLS_OUT", "/tls"),
        services=os.environ.get("TLS_SERVICES", ",".join(SERVICES)).split(","),
    )
