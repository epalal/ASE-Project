FROM postgres:17.11-alpine

# Only TLS connections with a password (design rule 7).
COPY pg_hba.conf /etc/postgresql/pg_hba.conf
# Runs once, when the database is first created: the Encounter Service's own login.
COPY 01-app-user.sh /docker-entrypoint-initdb.d/
COPY start.sh /usr/local/bin/start-encounter-db.sh

# Requirements §6: the database runs as the postgres user, never as root.
USER postgres
ENTRYPOINT ["sh", "/usr/local/bin/start-encounter-db.sh"]
