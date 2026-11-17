#!/bin/sh
set -e

CERT_FILE="/certs/server.pem"
KEY_FILE="/certs/server.key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Required TLS certificate files are missing from /certs" >&2
    exit 1
fi

exec gunicorn \
    --bind 0.0.0.0:5002 \
    --workers 2 \
    --preload \
    --certfile="$CERT_FILE" \
    --keyfile="$KEY_FILE" \
    "app:create_app()"
