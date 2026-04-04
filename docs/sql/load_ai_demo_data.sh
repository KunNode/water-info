#!/bin/bash
# =============================================================================
# AI Demo Data Loader
# =============================================================================
# This script loads AI-related demo data (emergency plans, actions, resources,
# notifications) into the PostgreSQL database.
#
# Prerequisites:
# 1. PostgreSQL container must be running
# 2. AI service must have been started at least once (to create tables)
#
# Usage:
#   ./load_ai_demo_data.sh                    # Use default connection
#   ./load_ai_demo_data.sh -h localhost -p 5432 -U waterinfo -d waterinfo
# =============================================================================

set -e

# Default connection parameters (match docker-compose.yml)
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_USER="${PGUSER:-waterinfo}"
DB_NAME="${PGDATABASE:-waterinfo}"
DB_PASSWORD="${PGPASSWORD:-${PG_PASSWORD:-123456}}"

# Parse command line arguments
while getopts "h:p:U:d:W:" opt; do
  case $opt in
    h) DB_HOST="$OPTARG" ;;
    p) DB_PORT="$OPTARG" ;;
    U) DB_USER="$OPTARG" ;;
    d) DB_NAME="$OPTARG" ;;
    W) DB_PASSWORD="$OPTARG" ;;
    *) echo "Usage: $0 [-h host] [-p port] [-U user] [-d database] [-W password]"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/seed_ai_demo_data.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file not found: $SQL_FILE"
    exit 1
fi

echo "=============================================="
echo "Loading AI Demo Data"
echo "=============================================="
echo "Host: $DB_HOST:$DB_PORT"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "SQL File: $SQL_FILE"
echo "=============================================="

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql command not found. Please install PostgreSQL client."
    echo ""
    echo "If running in Docker, use:"
    echo "  docker exec -i water-info-postgres psql -U waterinfo -d waterinfo < $SQL_FILE"
    exit 1
fi

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Execute SQL file
echo "Executing SQL..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

echo ""
echo "=============================================="
echo "AI Demo Data loaded successfully!"
echo "=============================================="
echo ""
echo "Loaded:"
echo "  - 4 Emergency Plans (draft, approved, executing, completed)"
echo "  - 18 Emergency Actions"
echo "  - 16 Resource Allocations"
echo "  - 20 Notification Records"
echo ""
echo "You can now:"
echo "  1. View plans at http://localhost/ai/plan"
echo "  2. Query AI at http://localhost/ai/command"
echo "=============================================="
