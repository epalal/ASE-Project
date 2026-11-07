#!/bin/sh
# Starts encounter-db with TLS, using the certificate that tls-init put in /certs.
# PostgreSQL accepts a private key only if it belongs to the postgres user and
# nobody else can read it, so the database uses its own copy of the key.
set -e
install -m 600 /certs/server.key /tmp/server.key
exec docker-entrypoint.sh postgres \
  -c ssl=on \
  -c ssl_cert_file=/certs/server.pem \
  -c ssl_key_file=/tmp/server.key \
  -c hba_file=/etc/postgresql/pg_hba.conf
