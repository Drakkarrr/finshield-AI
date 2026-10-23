#!/usr/bin/env bash
# FinShield AI — Database Backup Script (S4.5)
# Usage: ./backup.sh [backup_dir]
# Creates a timestamped PostgreSQL database backup with compression

set -euo pipefail

# Configuration
BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/finshield_${TIMESTAMP}.sql.gz"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Database configuration (from environment)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-finshield}"
DB_USER="${DB_USER:-finshield}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== FinShield AI Database Backup ===${NC}"
echo "Timestamp: ${TIMESTAMP}"
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "Backup file: ${BACKUP_FILE}"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Check if pg_dump is available
if ! command -v pg_dump &> /dev/null; then
    echo -e "${RED}Error: pg_dump is not installed or not in PATH${NC}"
    exit 1
fi

# Perform backup
echo "Starting backup..."
export PGPASSWORD="${DB_PASSWORD:-}"

pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="${BACKUP_FILE}" \
    2>&1 | while read line; do
        echo -e "${YELLOW}pg_dump:${NC} $line"
    done

unset PGPASSWORD

# Verify backup file was created
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file was not created${NC}"
    exit 1
fi

# Get backup file size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo ""
echo -e "${GREEN}✓ Backup completed successfully${NC}"
echo "  File: ${BACKUP_FILE}"
echo "  Size: ${BACKUP_SIZE}"
echo ""

# Generate checksum for integrity verification
echo "Generating checksum..."
CHECKSUM=$(sha256sum "${BACKUP_FILE}" | awk '{ print $1 }')
echo "${CHECKSUM}  ${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
echo -e "${GREEN}✓ Checksum:${NC} ${CHECKSUM}"
echo ""

# Clean up old backups (retention policy)
echo "Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "finshield_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete -print | wc -l)
echo -e "${GREEN}✓ Deleted ${DELETED_COUNT} old backup(s)${NC}"
echo ""

# List remaining backups
echo "Current backups:"
ls -lh "${BACKUP_DIR}"/finshield_*.sql.gz 2>/dev/null | tail -5 || echo "  (no backups found)"
echo ""

echo -e "${GREEN}=== Backup Complete ===${NC}"
echo ""
echo "To restore this backup:"
echo "  ./restore.sh ${BACKUP_FILE}"
echo ""
echo "To verify checksum:"
echo "  sha256sum -c ${BACKUP_FILE}.sha256"
