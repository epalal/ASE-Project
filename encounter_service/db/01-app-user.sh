#!/bin/sh
# Runs once, when encounter-db is first created. The Encounter Service gets its own
# login, which can use only this database, so it never needs the admin user
# ("Rules for all databases" in docs/architecture.md). psql quotes the password
# and the database name itself (:'...' and :"..."), so no value can break the SQL.
set -e
psql -v ON_ERROR_STOP=1 -v app_password="$ENCOUNTER_DB_PASSWORD" -v db_name="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE ROLE encounter_app LOGIN PASSWORD :'app_password';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO encounter_app;
GRANT USAGE, CREATE ON SCHEMA public TO encounter_app;
EOSQL
