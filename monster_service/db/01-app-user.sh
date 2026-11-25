#!/bin/sh
# Runs once when monster-db is first created: grants least-privilege access to monster_app
# when MONSTER_DB_PASSWORD is provided by the integrated stack.
set -e
if [ -z "${MONSTER_DB_PASSWORD:-}" ]; then
  exit 0
fi
psql -v ON_ERROR_STOP=1 -v app_password="$MONSTER_DB_PASSWORD" -v db_name="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE ROLE monster_app LOGIN PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO monster_app;
GRANT USAGE, CREATE ON SCHEMA public TO monster_app;
EOSQL
