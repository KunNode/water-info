#!/bin/sh
set -eu

export PATH="/usr/lib/postgresql16/bin:/usr/libexec/postgresql16:$PATH"

: "${PGDATA:=/var/lib/postgresql/data}"
: "${POSTGRES_DB:=postgres}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=postgres}"

mkdir -p "$PGDATA" /run/postgresql
chown -R postgres:postgres "$(dirname "$PGDATA")" "$PGDATA" /run/postgresql
chmod 700 "$PGDATA"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    su-exec postgres initdb -D "$PGDATA"
    echo "host all all all scram-sha-256" >> "$PGDATA/pg_hba.conf"
    echo "listen_addresses='*'" >> "$PGDATA/postgresql.conf"

    su-exec postgres pg_ctl -D "$PGDATA" -o "-c listen_addresses='localhost'" -w start

    su-exec postgres psql --dbname postgres -c "ALTER ROLE postgres WITH PASSWORD '${POSTGRES_PASSWORD}';"

    if [ "$POSTGRES_USER" != "postgres" ]; then
        if su-exec postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '${POSTGRES_USER}'" | grep -q 1; then
            su-exec postgres psql --dbname postgres -c "ALTER ROLE \"${POSTGRES_USER}\" WITH LOGIN SUPERUSER PASSWORD '${POSTGRES_PASSWORD}';"
        else
            su-exec postgres psql --dbname postgres -c "CREATE ROLE \"${POSTGRES_USER}\" LOGIN SUPERUSER PASSWORD '${POSTGRES_PASSWORD}';"
        fi
    fi

    if ! su-exec postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'" | grep -q 1; then
        su-exec postgres createdb -O "${POSTGRES_USER}" "${POSTGRES_DB}"
    fi

    su-exec postgres pg_ctl -D "$PGDATA" -m fast -w stop
fi

exec su-exec postgres "$@" -D "$PGDATA" -c listen_addresses='*'
