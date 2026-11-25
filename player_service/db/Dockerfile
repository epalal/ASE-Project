FROM postgres:17.11-alpine

RUN apk upgrade --no-cache && rm -f /usr/local/bin/gosu

COPY pg_hba.conf /etc/postgresql/pg_hba.conf
COPY 01-app-user.sh /docker-entrypoint-initdb.d/
COPY start.sh /usr/local/bin/start-player-db.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/01-app-user.sh /usr/local/bin/start-player-db.sh && \
    chmod 755 /docker-entrypoint-initdb.d/01-app-user.sh /usr/local/bin/start-player-db.sh

USER postgres
ENTRYPOINT ["sh", "/usr/local/bin/start-player-db.sh"]
