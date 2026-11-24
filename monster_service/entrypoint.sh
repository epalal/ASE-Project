#!/bin/sh
set -e

CERT_FILE="/certs/server.pem"
KEY_FILE="/certs/server.key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    CERT_FILE="/run/secrets/cert"
    KEY_FILE="/run/secrets/key"
fi

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "TLS certificate and key are not available." >&2
    exit 1
fi

exec gunicorn \
    --bind 0.0.0.0:5002 \
    --workers 2 \
    --preload \
    --certfile="$CERT_FILE" \
    --keyfile="$KEY_FILE" \
    "app:create_app()"