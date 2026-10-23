#!/bin/sh
# FinShield Postgres restore (S4.5). Runbook: DEPLOYMENT.md "Backup and restore".
#
#   DATABASE_URL=postgresql://user:pass@host:5432/db scripts/restore.sh finshield-<ts>.dump
#
# Restores into an EMPTY database by default. Set RESTORE_CLEAN=yes to drop and replace the
# objects of an existing one (destructive). Verifies the .sha256 next to the archive when present
# and recreates the cluster role finshield_app, which pg_dump does not include. Privileges are not
# restored from the archive (they name the source cluster's roles); the grants of migration 0005
# are re-applied for the restoring role instead. RLS policies and triggers come from the archive.
# Afterwards run `python -m scripts.audit_check` with the SAME DATA_ENCRYPTION_KEY as the source.
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
archive="${1:?usage: restore.sh <archive.dump>}"
[ -f "$archive" ] || { echo "restore: $archive not found" >&2; exit 2; }

if [ -f "$archive.sha256" ]; then
  (cd "$(dirname "$archive")" && sha256sum -c "$(basename "$archive").sha256")
else
  echo "restore: no $archive.sha256, skipping checksum" >&2
fi
pg_restore --list "$archive" >/dev/null

tables=$(psql "$DATABASE_URL" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
clean=""
if [ "$tables" -gt 0 ]; then
  if [ "${RESTORE_CLEAN:-}" != "yes" ]; then
    echo "restore: target has $tables table(s). Restore into an empty database, or set RESTORE_CLEAN=yes." >&2
    exit 2
  fi
  clean="--clean --if-exists"
fi

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'finshield_app') THEN
    CREATE ROLE finshield_app NOLOGIN;
  END IF;
  IF NOT pg_has_role(CURRENT_USER, 'finshield_app', 'MEMBER') THEN
    GRANT finshield_app TO CURRENT_USER;
  END IF;
END
$$;
SQL

# shellcheck disable=SC2086
pg_restore --no-owner --no-acl --exit-on-error --single-transaction $clean --dbname="$DATABASE_URL" "$archive"

# Same grants as migration 0005, for the role that now owns the restored objects.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q <<'SQL'
GRANT USAGE ON SCHEMA public TO finshield_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO finshield_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO finshield_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO finshield_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO finshield_app;
SQL
echo "restore: done, schema revision $(psql "$DATABASE_URL" -tAc 'SELECT version_num FROM alembic_version')"
