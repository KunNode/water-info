ARG DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/
FROM ${DOCKER_REGISTRY_PREFIX}alpine:3.20

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    apk add --no-cache postgresql16 postgresql16-client postgresql16-contrib su-exec bash

ENV PATH="/usr/lib/postgresql16/bin:/usr/libexec/postgresql16:$PATH" \
    PGDATA=/var/lib/postgresql/data

COPY docker/postgres/entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    mkdir -p /var/lib/postgresql/data /run/postgresql && \
    chown -R postgres:postgres /var/lib/postgresql /run/postgresql

VOLUME ["/var/lib/postgresql/data"]
EXPOSE 5432

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
