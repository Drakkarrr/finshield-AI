#!/usr/bin/env bash
# FinShield AI — Database Restore Script (S4.5)
# Usage: ./restore.sh <backup_file> [target_db]
# Restores a PostgreSQL database from a backup file

set -euo pipefail

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file> [target_db]"
    echo ""
    echo "Arguments:"
    echo "  backup_file  Path to the backup file (.sql.gz or .dump)"
    echo "  target_db    Target database name (default: finshield_restored)"
    echo ""
    echo "Example:"
    echo "  $0 ./backups/finshield_20261024_120000.sql.gz"
    exit 1
fi

# Configuration
BACKUP_FILE="$1"
TARGET_DB="${2:-finshield_restored}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Database configuration (from environment)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-finshield}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== FinShield AI Database Restore ===${NC}"
echo "Timestamp: ${TIMESTAMP}"
echo "Backup file: ${BACKUP_FILE}"
echo "Target database: ${TARGET_DB}@${DB_HOST}:${DB_PORT}"
echo ""

# Verify backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

# Verify checksum if checksum file exists
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "Verifying backup integrity..."
    if sha256sum -c "${CHECKSUM_FILE}" --quiet; then
        echo -e "${GREEN}✓ Checksum verified${NC}"
    else
        echo -e "${RED}Error: Checksum verification failed! Backup may be corrupted.${NC}"
        exit 1
    fi
    echo ""
fi

# Check if pg_restore is available
if ! command -v pg_restore &> /dev/null; then
    echo -e "${RED}Error: pg_restore is not installed or not in PATH${NC}"
    exit 1
fi

# Warn about data loss
echo -e "${YELLOW}WARNING: This will restore the database to the state in the backup.${NC}"
echo -e "${YELLOW}Any data created after the backup will be lost.${NC}"
echo ""
read -p "Continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi
echo ""

# Create target database if it doesn't exist
echo "Creating target database..."
export PGPASSWORD="${DB_PASSWORD:-}"

# Drop database if it exists (ignore errors)
dropdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" --if-exists "${TARGET_DB}" 2>/dev/null || true

# Create new database
createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${TARGET_DB}" || {
    echo -e "${RED}Error: Failed to create database ${TARGET_DB}${NC}"
    unset PGPASSWORD
    exit 1
}

echo -e "${GREEN}✓ Database created${NC}"
echo ""

# Perform restore
echo "Starting restore..."
pg_restore \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${TARGET_DB}" \
    --verbose \
    --no-owner \
    --no-privileges \
    "${BACKUP_FILE}" \
    2>&1 | while read line; do
        echo -e "${YELLOW}pg_restore:${NC} $line"
    done || {
        echo -e "${RED}Error: Restore failed${NC}"
        unset PGPASSWORD
        exit 1
    }

unset PGPASSWORD

echo ""
echo -e "${GREEN}✓ Restore completed successfully${NC}"
echo ""

# Run Alembic migrations to bring schema up to date
echo "Running Alembic migrations to update schema..."
cd "$(dirname "$0")/../backend"
ALEMBIC_CONFIG="./alembic.ini"

if [ -f "${ALEMBIC_CONFIG}" ]; then
    # Set database URL for Alembic
    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD:-}@${DB_HOST}:${DB_PORT}/${TARGET_DB}"
    
    python -m alembic -c "${ALEMBIC_CONFIG}" upgrade head || {
        echo -e "${YELLOW}Warning: Alembic migration failed (may be expected if backup is recent)${NC}"
    }
    
    unset DATABASE_URL
else
    echo -e "${YELLOW}Warning: Alembic config not found, skipping migrations${NC}"
fi

echo ""

# Verify audit chain integrity
echo "Verifying audit chain integrity..."
cd "$(dirname "$0")/../backend"
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD:-}@${DB_HOST}:${DB_PORT}/${TARGET_DB}"
export APP_ENV="production"

python -c "
from app.database import SessionLocal
from app.api.audit import verify_chain

db = SessionLocal()
try:
    result = verify_chain(db)
    if result['valid']:
        print('✓ Audit chain integrity verified')
        print(f'  Total entries: {result[\"total_entries\"]}')
    else:
        print('✗ Audit chain integrity check FAILED')
        print(f'  Errors: {result[\"errors\"]}')
        exit(1)
finally:
    db.close()
" || {
    echo -e "${RED}Error: Audit chain verification failed${NC}"
    unset DATABASE_URL
    exit 1
}

unset DATABASE_URL
unset APP_ENV

echo ""
echo -e "${GREEN}=== Restore Complete ===${NC}"
echo ""
echo "Database restored to: ${TARGET_DB}"
echo ""
echo "To connect to the restored database:"
echo "  psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${TARGET_DB}"
echo ""
echo "To swap databases (caution: this will replace production):"
echo "  dropdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} finshield"
echo "  createdb -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} finshield"
echo "  pg_restore -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d finshield ${BACKUP_FILE}"
