FROM postgres:17.11-alpine

# Keep the database server on a patched base and run it as the postgres user.
RUN apk upgrade --no-cache
COPY pg_hba.conf /etc/postgresql/pg_hba.conf
COPY 01-app-user.sh /docker-entrypoint-initdb.d/
COPY start.sh /usr/local/bin/start-monster-db.sh
USER postgres
ENTRYPOINT ["sh", "/usr/local/bin/start-monster-db.sh"]
