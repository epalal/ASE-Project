#!/bin/sh
set -e

CERT_FILE="/run/secrets/cert"
KEY_FILE="/run/secrets/key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "No mounted TLS secrets found. Generating self-signed certificates for standalone mode..."
    mkdir -p /tmp/certs
    CERT_FILE="/tmp/certs/server.pem"
    KEY_FILE="/tmp/certs/server.key"
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=localhost" 2>/dev/null
fi

exec gunicorn \
    --bind 0.0.0.0:5002 \
    --workers 2 \
    --preload \
    --certfile="$CERT_FILE" \
    --keyfile="$KEY_FILE" \
    "app:create_app()"