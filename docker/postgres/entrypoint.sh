#!/bin/bash
set -e

# Default values
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-$POSTGRES_USER}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

# Initialize database if not exists
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database..."
    mkdir -p "$PGDATA"
    chown -R postgres:postgres "$PGDATA"

    su-exec postgres initdb --username="$POSTGRES_USER" --pwfile=<(echo "$POSTGRES_PASSWORD") --encoding=UTF8 --locale=C

    # Configure password auth
    {
        echo "host all all 0.0.0.0/0 md5"
        echo "host all all ::/0 md5"
    } >> "$PGDATA/pg_hba.conf"

    # Tune for development
    {
        echo "listen_addresses = '*'"
        echo "shared_buffers = 256MB"
        echo "max_connections = 200"
        echo "log_statement = 'none'"
    } >> "$PGDATA/postgresql.conf"

    # Start temporarily to create DB and run init scripts
    su-exec postgres pg_ctl -D "$PGDATA" -o "-c listen_addresses=''" -w start

    if [ "$POSTGRES_DB" != "postgres" ]; then
        su-exec postgres createdb -O "$POSTGRES_USER" "$POSTGRES_DB"
    fi

    # Run init scripts
    for f in /docker-entrypoint-initdb.d/*; do
        case "$f" in
            *.sql)
                echo "Running $f..."
                su-exec postgres psql -v ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" -f "$f"
                ;;
            *.sql.gz)
                echo "Running $f..."
                gunzip -c "$f" | su-exec postgres psql -v ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
                ;;
            *)
                echo "Skipping $f"
                ;;
        esac
    done

    su-exec postgres pg_ctl -D "$PGDATA" -m fast -w stop
    echo "Database initialization complete."
fi

# Hand off to CMD
exec su-exec postgres "$@"
