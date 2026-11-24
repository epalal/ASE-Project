FROM postgres:15-alpine

COPY db-entrypoint.sh /usr/local/bin/monster-db-entrypoint.sh
RUN chmod 755 /usr/local/bin/monster-db-entrypoint.sh

USER root
ENTRYPOINT ["/usr/local/bin/monster-db-entrypoint.sh"]
