#!/usr/bin/env bash
# FinShield AI — Backup/Restore Test Script (S4.5)
# Tests the backup and restore process to ensure it works correctly

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== FinShield AI Backup/Restore Test ===${NC}"
echo ""

# Configuration
TEST_DB="finshield_backup_test"
BACKUP_DIR="./test_backups"
SCRIPTS_DIR="$(dirname "$0")"

# Cleanup function
cleanup() {
    echo ""
    echo -e "${BLUE}Cleaning up test artifacts...${NC}"
    
    # Drop test database
    dropdb --if-exists "${TEST_DB}" 2>/dev/null || true
    dropdb --if-exists "${TEST_DB}_restored" 2>/dev/null || true
    
    # Remove test backups
    rm -rf "${BACKUP_DIR}"
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v pg_dump &> /dev/null; then
    echo -e "${RED}✗ pg_dump not found${NC}"
    exit 1
fi

if ! command -v pg_restore &> /dev/null; then
    echo -e "${RED}✗ pg_restore not found${NC}"
    exit 1
fi

if [ ! -f "${SCRIPTS_DIR}/backup.sh" ]; then
    echo -e "${RED}✗ backup.sh not found${NC}"
    exit 1
fi

if [ ! -f "${SCRIPTS_DIR}/restore.sh" ]; then
    echo -e "${RED}✗ restore.sh not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Step 1: Create test database
echo -e "${BLUE}Step 1: Creating test database...${NC}"
createdb "${TEST_DB}" || {
    echo -e "${RED}✗ Failed to create test database${NC}"
    exit 1
}
echo -e "${GREEN}✓ Test database created${NC}"
echo ""

# Step 2: Populate with test data
echo -e "${BLUE}Step 2: Populating test database...${NC}"
psql -d "${TEST_DB}" <<'EOF'
-- Create test tables
CREATE TABLE test_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE test_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES test_users(id),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert test data
INSERT INTO test_users (email) VALUES
    ('user1@example.com'),
    ('user2@example.com'),
    ('user3@example.com');

INSERT INTO test_transactions (user_id, amount, status) VALUES
    (1, 100.00, 'approved'),
    (1, 250.50, 'approved'),
    (2, 75.25, 'flagged'),
    (3, 500.00, 'blocked');

-- Verify data
SELECT 'Users: ' || COUNT(*) FROM test_users;
SELECT 'Transactions: ' || COUNT(*) FROM test_transactions;
EOF

echo -e "${GREEN}✓ Test data populated${NC}"
echo ""

# Step 3: Create backup
echo -e "${BLUE}Step 3: Creating backup...${NC}"
mkdir -p "${BACKUP_DIR}"

# Set environment for backup script
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${TEST_DB}"
export DB_USER="${DB_USER:-$(whoami)}"

"${SCRIPTS_DIR}/backup.sh" "${BACKUP_DIR}" || {
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
}

# Find the backup file
BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/finshield_*.sql.gz | head -1)

if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}✗ Backup file not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backup created: ${BACKUP_FILE}${NC}"
echo ""

# Step 4: Verify checksum
echo -e "${BLUE}Step 4: Verifying checksum...${NC}"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [ ! -f "${CHECKSUM_FILE}" ]; then
    echo -e "${RED}✗ Checksum file not found${NC}"
    exit 1
fi

if sha256sum -c "${CHECKSUM_FILE}" --quiet; then
    echo -e "${GREEN}✓ Checksum verified${NC}"
else
    echo -e "${RED}✗ Checksum verification failed${NC}"
    exit 1
fi
echo ""

# Step 5: Restore backup
echo -e "${BLUE}Step 5: Restoring backup...${NC}"
RESTORED_DB="${TEST_DB}_restored"

# Auto-confirm restore (pipe "yes" to script)
echo "yes" | "${SCRIPTS_DIR}/restore.sh" "${BACKUP_FILE}" "${RESTORED_DB}" || {
    echo -e "${RED}✗ Restore failed${NC}"
    exit 1
}

echo -e "${GREEN}✓ Backup restored${NC}"
echo ""

# Step 6: Verify restored data
echo -e "${BLUE}Step 6: Verifying restored data...${NC}"

USER_COUNT=$(psql -d "${RESTORED_DB}" -t -c "SELECT COUNT(*) FROM test_users;" | xargs)
TX_COUNT=$(psql -d "${RESTORED_DB}" -t -c "SELECT COUNT(*) FROM test_transactions;" | xargs)

if [ "${USER_COUNT}" != "3" ]; then
    echo -e "${RED}✗ User count mismatch: expected 3, got ${USER_COUNT}${NC}"
    exit 1
fi

if [ "${TX_COUNT}" != "4" ]; then
    echo -e "${RED}✗ Transaction count mismatch: expected 4, got ${TX_COUNT}${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Data verified: ${USER_COUNT} users, ${TX_COUNT} transactions${NC}"
echo ""

# Step 7: Compare original and restored
echo -e "${BLUE}Step 7: Comparing original and restored databases...${NC}"

ORIG_SUM=$(psql -d "${TEST_DB}" -t -c "SELECT SUM(amount) FROM test_transactions;" | xargs)
REST_SUM=$(psql -d "${RESTORED_DB}" -t -c "SELECT SUM(amount) FROM test_transactions;" | xargs)

if [ "${ORIG_SUM}" != "${REST_SUM}" ]; then
    echo -e "${RED}✗ Data mismatch: original sum ${ORIG_SUM}, restored sum ${REST_SUM}${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Databases match (sum: ${ORIG_SUM})${NC}"
echo ""

# Step 8: Test backup size
echo -e "${BLUE}Step 8: Checking backup size...${NC}"
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo -e "${GREEN}✓ Backup size: ${BACKUP_SIZE}${NC}"
echo ""

# Summary
echo -e "${GREEN}=== All Tests Passed ===${NC}"
echo ""
echo "Summary:"
echo "  ✓ Backup creation"
echo "  ✓ Checksum verification"
echo "  ✓ Restore process"
echo "  ✓ Data integrity"
echo "  ✓ Database comparison"
echo ""
echo "Backup/restore functionality is working correctly."
echo ""
