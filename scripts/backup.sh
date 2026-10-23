#!/bin/sh
# FinShield Postgres backup (S4.5). Runbook: DEPLOYMENT.md "Backup and restore".
#
#   DATABASE_URL=postgresql://user:pass@host:5432/db scripts/backup.sh
#
# Writes a pg_dump custom-format archive plus a .sha256 to BACKUP_DIR, checks the archive is
# readable, optionally copies both to BACKUP_S3_URI (needs the aws CLI), then prunes local
# archives older than BACKUP_RETENTION_DAYS while always keeping the newest BACKUP_MIN_KEEP.
# Connect as the database owner/superuser: under row-level security a lesser role would dump
# only the rows it can see.
#
# Not in the archive, back these up separately: DATA_ENCRYPTION_KEY (encrypted columns and the
# audit signing key derive from it) and the cluster role finshield_app (restore.sh recreates it).
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set}"
dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-35}"
min_keep="${BACKUP_MIN_KEEP:-7}"

mkdir -p "$dir"
name="finshield-$(date -u +%Y%m%dT%H%M%SZ).dump"
tmp="$dir/.$name.partial"
trap 'rm -f "$tmp"' EXIT

pg_dump --format=custom --compress=6 --no-owner --dbname="$DATABASE_URL" --file="$tmp"
pg_restore --list "$tmp" >/dev/null  # fails on a truncated or corrupt archive
mv "$tmp" "$dir/$name"
(cd "$dir" && sha256sum "$name" > "$name.sha256")
echo "backup: $dir/$name ($(du -h "$dir/$name" | cut -f1))"

if [ -n "${BACKUP_S3_URI:-}" ]; then
  aws s3 cp "$dir/$name" "$BACKUP_S3_URI/$name"
  aws s3 cp "$dir/$name.sha256" "$BACKUP_S3_URI/$name.sha256"
  echo "backup: copied to $BACKUP_S3_URI"
fi

# Retention: newest first (names are UTC timestamps); never delete the newest $min_keep, then drop anything older than the window.
find "$dir" -maxdepth 1 -name "finshield-*.dump" | sort -r | tail -n +"$((min_keep + 1))" | while read -r old; do
  if [ -n "$(find "$old" -mtime +"$retention_days")" ]; then
    rm -f "$old" "$old.sha256"
    echo "backup: pruned $(basename "$old")"
  fi
done
