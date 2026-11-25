#!/bin/sh
# Runs once when player-db is first created: grants least-privilege access to player_app.
set -e
psql -v ON_ERROR_STOP=1 -v app_password="$PLAYER_DB_PASSWORD" -v db_name="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE ROLE player_app LOGIN PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO player_app;
GRANT USAGE, CREATE ON SCHEMA public TO player_app;
EOSQL
