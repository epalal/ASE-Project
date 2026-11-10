import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone, timedelta

# 1. Genera una vera coppia di chiavi RSA
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()
pub_pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode('utf-8')

print("\n=== 1. METTI QUESTO NEL DOCKER-COMPOSE.YAML (Sotto JWT_PUBLIC_KEY: |) ===")
print(pub_pem)

# 2. Genera un token valido per un anno che rispetta le regole del Gateway
payload = {
    "sub": "bruno_player_01",
    "aud": "monster-tamers",
    "iss": "player-service",
    "exp": datetime.now(timezone.utc) + timedelta(days=365)
}
token = jwt.encode(payload, private_key, algorithm="RS256")

print("=== 2. METTI QUESTO IN BRUNO (Scheda Auth -> Bearer Token) ===")
print(token)
print("==============================================================\n")