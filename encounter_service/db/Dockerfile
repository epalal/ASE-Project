FROM postgres:17.11-alpine

# Lab 9: the security fixes Alpine published after the base image was built
# (trivy reports them as fixable). Runs as root, before USER postgres.
# gosu only switches from root to postgres when the container starts as root;
# this one always starts as postgres (USER below), so gosu is never used. It is
# built with an old Go version that trivy reports, so it is removed.
RUN apk upgrade --no-cache && rm /usr/local/bin/gosu

# Only TLS connections with a password (design rule 7).
COPY pg_hba.conf /etc/postgresql/pg_hba.conf
# Runs once, when the database is first created: the Encounter Service's own login.
COPY 01-app-user.sh /docker-entrypoint-initdb.d/
COPY start.sh /usr/local/bin/start-encounter-db.sh

# Requirements §6: the database runs as the postgres user, never as root.
USER postgres
ENTRYPOINT ["sh", "/usr/local/bin/start-encounter-db.sh"]
