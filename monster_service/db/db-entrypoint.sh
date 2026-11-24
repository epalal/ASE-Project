#!/bin/sh
set -eu

: "${POSTGRES_SSL_CERT_FILE:?PostgreSQL TLS certificate is required}"
: "${POSTGRES_SSL_KEY_FILE:?PostgreSQL TLS private key is required}"

ssl_dir=/var/lib/postgresql/tls
mkdir -p "$ssl_dir"
cp "$POSTGRES_SSL_CERT_FILE" "$ssl_dir/server.pem"
cp "$POSTGRES_SSL_KEY_FILE" "$ssl_dir/server.key"
chown postgres:postgres "$ssl_dir" "$ssl_dir/server.pem" "$ssl_dir/server.key"
chmod 700 "$ssl_dir"
chmod 644 "$ssl_dir/server.pem"
chmod 600 "$ssl_dir/server.key"

exec /usr/local/bin/docker-entrypoint.sh postgres \
    -c ssl=on \
    -c ssl_cert_file="$ssl_dir/server.pem" \
    -c ssl_key_file="$ssl_dir/server.key"
