FROM postgres:17.11-alpine

RUN apk upgrade --no-cache && rm /usr/local/bin/gosu
COPY pg_hba.conf /etc/postgresql/pg_hba.conf
COPY 01-app-user.sh /docker-entrypoint-initdb.d/
COPY start.sh /usr/local/bin/start-encounter-db.sh
RUN sed -i 's/\r$//' /usr/local/bin/start-encounter-db.sh /docker-entrypoint-initdb.d/01-app-user.sh
USER postgres
ENTRYPOINT ["sh", "/usr/local/bin/start-encounter-db.sh"]
