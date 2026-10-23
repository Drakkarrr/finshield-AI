# FinShield AI — Backup & Restore Runbook (S4.5)

## Purpose

This runbook provides step-by-step instructions for FinShield AI operations team to perform database backup and restore operations. Follow these procedures exactly to ensure data integrity and compliance.

## Prerequisites

- Access to production database server
- `pg_dump` and `pg_restore` utilities installed
- Database credentials (stored in Vault/Secrets Manager)
- Sufficient disk space for backups
- Network access to database and storage

## Quick Reference

| Operation | Command | Estimated Time |
|-----------|---------|----------------|
| Create backup | `./scripts/backup.sh` | 5-15 minutes |
| Restore backup | `./scripts/restore.sh <file>` | 10-30 minutes |
| Verify checksum | `sha256sum -c <file>.sha256` | < 1 minute |
| List backups | `ls -lh backups/` | < 1 minute |

---

## Procedure 1: Create Manual Backup

### When to Use
- Before major deployments
- Before schema migrations
- Upon request from compliance/legal
- As part of scheduled maintenance

### Steps

1. **Prepare environment**
   ```bash
   # SSH to backup server
   ssh backup@finshield-prod
   
   # Navigate to scripts directory
   cd /opt/finshield
   
   # Load database credentials
   source /etc/finshield/db-credentials.env
   ```

2. **Create backup**
   ```bash
   # Create backup with default retention (30 days)
   ./scripts/backup.sh /backups/manual
   
   # Or specify custom retention
   BACKUP_RETENTION_DAYS=90 ./scripts/backup.sh /backups/manual
   ```

3. **Verify backup**
   ```bash
   # Check backup file exists
   ls -lh /backups/manual/finshield_*.sql.gz
   
   # Verify checksum
   sha256sum -c /backups/manual/finshield_*.sha256
   
   # Check backup size (should be similar to previous backups)
   du -h /backups/manual/finshield_*.sql.gz | tail -5
   ```

4. **Document backup**
   ```bash
   # Record in backup log
   echo "$(date -Iseconds) - Manual backup created by $(whoami)" >> /var/log/finshield/backups.log
   ```

5. **Notify team** (if requested by compliance)
   ```
   To: compliance@finshield.ai
   Subject: Manual Backup Created - [DATE]
   
   A manual backup has been created as requested.
   
   Backup file: /backups/manual/finshield_[TIMESTAMP].sql.gz
   Size: [SIZE]
   Checksum: [CHECKSUM]
   Retention: [DAYS] days
   ```

### Expected Output
```
=== FinShield AI Database Backup ===
Timestamp: 20261024_120000
Database: finshield@localhost:5432
Backup file: /backups/manual/finshield_20261024_120000.sql.gz

Starting backup...
✓ Backup completed successfully
  File: /backups/manual/finshield_20261024_120000.sql.gz
  Size: 1.2G

Generating checksum...
✓ Checksum: a1b2c3d4e5f6...

Cleaning up backups older than 30 days...
✓ Deleted 0 old backup(s)

=== Backup Complete ===
```

### Troubleshooting

**Error: pg_dump: command not found**
- Install PostgreSQL client: `apt-get install postgresql-client`

**Error: connection refused**
- Check database is running: `systemctl status postgresql`
- Verify credentials in `/etc/finshield/db-credentials.env`
- Check firewall rules allow connections

**Error: permission denied**
- Ensure user has SELECT permissions on all tables
- Check `pg_hba.conf` allows connections from backup server

**Error: disk full**
- Clean up old backups: `find /backups -name "*.sql.gz" -mtime +30 -delete`
- Expand disk or move to larger storage

---

## Procedure 2: Restore from Backup

### When to Use
- After accidental data deletion
- After application bug corrupts data
- After database corruption
- As part of disaster recovery
- For compliance/legal hold restoration

### Steps

1. **Assess situation**
   ```bash
   # Determine what needs to be restored
   # - Full database?
   # - Specific tables?
   # - Point in time?
   
   # Identify appropriate backup
   ls -lht /backups/daily/ | head -10
   ```

2. **Prepare for restore**
   ```bash
   # SSH to database server
   ssh db@finshield-prod
   
   # Stop application (prevent writes during restore)
   sudo systemctl stop finshield-backend
   
   # Notify users
   echo "Database restore in progress. ETA: 30 minutes." > /var/www/finshield/maintenance.html
   ```

3. **Verify backup integrity**
   ```bash
   # Navigate to backup directory
   cd /backups/daily
   
   # Verify checksum
   sha256sum -c finshield_20261024_000000.sql.gz.sha256
   
   # Expected output: finshield_20261024_000000.sql.gz: OK
   ```

4. **Restore database**
   ```bash
   # Load credentials
   source /etc/finshield/db-credentials.env
   
   # Restore to new database first (safe approach)
   /opt/finshield/scripts/restore.sh /backups/daily/finshield_20261024_000000.sql.gz finshield_restored
   
   # When prompted, type "yes" to confirm
   ```

5. **Verify restore**
   ```bash
   # Connect to restored database
   psql -h localhost -U finshield -d finshield_restored
   
   # Check table counts
   SELECT COUNT(*) FROM transactions;
   SELECT COUNT(*) FROM audit_logs;
   
   # Verify audit chain
   \q
   
   # Run audit chain verification
   cd /opt/finshield/backend
   export DATABASE_URL="postgresql://finshield:${DB_PASSWORD}@localhost:5432/finshield_restored"
   python -c "from app.database import SessionLocal; from app.api.audit import verify_chain; db = SessionLocal(); print(verify_chain(db)); db.close()"
   ```

6. **Swap databases** (if restore is successful)
   ```bash
   # WARNING: This will replace production database!
   
   # Drop production database
   dropdb -h localhost -U finshield finshield
   
   # Rename restored database
   psql -h localhost -U finshield -c "ALTER DATABASE finshield_restored RENAME TO finshield;"
   
   # Verify
   psql -h localhost -U finshield -d finshield -c "SELECT COUNT(*) FROM transactions;"
   ```

7. **Restart application**
   ```bash
   # Start application
   sudo systemctl start finshield-backend
   
   # Check health
   curl http://localhost:8091/api/health
   
   # Remove maintenance page
   rm /var/www/finshield/maintenance.html
   ```

8. **Document restore**
   ```bash
   # Record in restore log
   cat >> /var/log/finshield/restores.log <<EOF
   $(date -Iseconds) - Database restored by $(whoami)
   Backup file: /backups/daily/finshield_20261024_000000.sql.gz
   Reason: [REASON]
   Downtime: [START] to [END]
   Data loss: [DESCRIPTION]
   EOF
   ```

9. **Notify stakeholders**
   ```
   To: stakeholders@finshield.ai
   Subject: Database Restore Complete - [DATE]
   
   The database has been successfully restored.
   
   Backup used: finshield_20261024_000000.sql.gz
   Restore time: [DURATION]
   Data loss: [DESCRIPTION]
   
   All systems are operational.
   ```

### Expected Output
```
=== FinShield AI Database Restore ===
Timestamp: 20261024_130000
Backup file: /backups/daily/finshield_20261024_000000.sql.gz
Target database: finshield_restored@localhost:5432

Verifying backup integrity...
✓ Checksum verified

WARNING: This will restore the database to the state in the backup.
Any data created after the backup will be lost.

Continue? (yes/no): yes

Creating target database...
✓ Database created

Starting restore...
✓ Restore completed successfully

Running Alembic migrations to update schema...
Verifying audit chain integrity...
✓ Audit chain integrity verified
  Total entries: 12345

=== Restore Complete ===

Database restored to: finshield_restored
```

### Troubleshooting

**Error: checksum verification failed**
- Backup file is corrupted
- Download backup from alternative source (S3, offsite)
- Do NOT restore from corrupted backup

**Error: database already exists**
- Drop existing database: `dropdb finshield_restored`
- Or restore to different database name

**Error: pg_restore: error**
- Check PostgreSQL version compatibility
- Try with `--clean` flag to drop objects before creating
- Review pg_restore output for specific errors

**Error: audit chain verification failed**
- Backup may be from before audit chain feature was added
- Manually verify critical audit entries
- Consult security team before proceeding

**Error: application won't start after restore**
- Check database connection strings
- Verify Alembic migrations ran successfully
- Check application logs: `journalctl -u finshield-backend`

---

## Procedure 3: Emergency Disaster Recovery

### When to Use
- Complete data center failure
- Ransomware attack
- Catastrophic data corruption
- All local backups lost

### Steps

1. **Declare disaster**
   ```bash
   # Notify incident response team
   # Activate disaster recovery plan
   # Set up incident bridge call
   ```

2. **Assess damage**
   - Determine what data/systems are affected
   - Identify last known good state
   - Estimate recovery time

3. **Retrieve offsite backup**
   ```bash
   # Download from S3 Glacier
   aws s3 cp s3://finshield-backups-glacier/finshield_20261024_000000.sql.gz /tmp/
   
   # Or from secondary region
   scp backup@finshield-dr:/backups/finshield_20261024_000000.sql.gz /tmp/
   ```

4. **Restore to new infrastructure**
   ```bash
   # Provision new database server
   # Install PostgreSQL
   # Configure network/security
   
   # Restore backup
   /opt/finshield/scripts/restore.sh /tmp/finshield_20261024_000000.sql.gz finshield
   ```

5. **Rebuild application tier**
   ```bash
   # Deploy application from CI/CD
   # Configure environment variables
   # Update DNS to point to new infrastructure
   ```

6. **Validate and test**
   - Run full test suite
   - Verify data integrity
   - Test critical user flows
   - Check audit log continuity

7. **Monitor closely**
   - Watch for errors in logs
   - Monitor performance
   - Be ready for additional issues

8. **Post-incident review**
   - Document timeline
   - Identify root cause
   - Update procedures
   - Schedule follow-up

---

## Procedure 4: Verify Backup Integrity

### When to Use
- Weekly scheduled check
- After backup failures
- Before major restore
- Compliance audit

### Steps

1. **List recent backups**
   ```bash
   ls -lht /backups/daily/ | head -10
   ```

2. **Verify checksums**
   ```bash
   # Verify all checksums in directory
   cd /backups/daily/
   for f in *.sha256; do sha256sum -c "$f"; done
   ```

3. **Test restore to temporary database**
   ```bash
   # Restore to test database
   /opt/finshield/scripts/restore.sh /backups/daily/finshield_20261024_000000.sql.gz finshield_test
   
   # Verify data
   psql -h localhost -U finshield -d finshield_test -c "SELECT COUNT(*) FROM transactions;"
   
   # Clean up
   dropdb finshield_test
   ```

4. **Verify audit chain**
   ```bash
   cd /opt/finshield/backend
   export DATABASE_URL="postgresql://finshield:${DB_PASSWORD}@localhost:5432/finshield_test"
   python -c "from app.database import SessionLocal; from app.api.audit import verify_chain; db = SessionLocal(); result = verify_chain(db); print('Valid:', result['valid']); db.close()"
   ```

5. **Document results**
   ```bash
   echo "$(date -Iseconds) - Backup verification passed" >> /var/log/finshield/backup-verification.log
   ```

---

## Procedure 5: Manage Backup Retention

### When to Use
- Monthly cleanup
- Storage capacity issues
- Compliance requirement changes

### Steps

1. **Review current retention**
   ```bash
   # Count backups by age
   find /backups/daily/ -name "*.sql.gz" -mtime -7 | wc -l  # Last 7 days
   find /backups/daily/ -name "*.sql.gz" -mtime -30 | wc -l # Last 30 days
   find /backups/daily/ -name "*.sql.gz" -mtime +30 | wc -l # Older than 30 days
   ```

2. **Check storage usage**
   ```bash
   du -sh /backups/*
   df -h /backups
   ```

3. **Clean up old backups**
   ```bash
   # Delete backups older than retention period
   find /backups/daily/ -name "*.sql.gz" -mtime +30 -delete
   find /backups/daily/ -name "*.sha256" -mtime +30 -delete
   
   # Verify cleanup
   df -h /backups
   ```

4. **Archive to cold storage** (if needed)
   ```bash
   # Move to S3 Glacier
   aws s3 mv /backups/monthly/ s3://finshield-backups-glacier/monthly/ --recursive
   
   # Or to offsite location
   rsync -avz /backups/monthly/ backup@offsite:/backups/monthly/
   ```

---

## Contacts & Escalation

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Primary On-Call | [ROTATE] | ops@finshield.ai | +1-555-0100 |
| Database Admin | DBA Team | dba@finshield.ai | +1-555-0101 |
| Security Incident | Security Team | security@finshield.ai | +1-555-0102 |
| Management | CTO | cto@finshield.ai | +1-555-0103 |

## Related Documentation

- [Retention Matrix](./RETENTION_MATRIX.md)
- [Disaster Recovery Plan](./DISASTER_RECOVERY.md)
- [Database Architecture](../architecture/DATABASE.md)
- [Security Policy](../security/POLICY.md)

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-24 | FinShield AI | Initial runbook |
