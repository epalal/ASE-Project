#!/bin/sh
set -e
install -m 600 /certs/server.key /tmp/server.key
exec docker-entrypoint.sh postgres \
  -c ssl=on \
  -c ssl_cert_file=/certs/server.pem \
  -c ssl_key_file=/tmp/server.key \
  -c hba_file=/etc/postgresql/pg_hba.conf
