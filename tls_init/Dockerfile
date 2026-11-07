FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY make_certs.py .

# The certificate group (10000): every service joins it in Docker Compose to read
# its own private key. Each folder under /tls becomes one Docker volume, and a new
# volume takes the owner of its folder in this image, so tls-init can write into
# every volume without running as root.
RUN groupadd --gid 10000 certs \
 && useradd --uid 10001 --gid certs --no-create-home tlsinit \
 && mkdir -p /tls/ca /tls/gateway /tls/player-service /tls/monster-service \
             /tls/encounter-service /tls/player-db /tls/monster-db /tls/encounter-db \
 && chown -R tlsinit:certs /tls
USER tlsinit

ENV TLS_OUT=/tls
CMD ["python", "make_certs.py"]
