# FinShield AI — Backup Retention Matrix (S4.5)

## Overview

This document defines the backup retention policy for FinShield AI production databases. The retention matrix balances regulatory compliance, disaster recovery requirements, and storage costs.

## Regulatory Requirements

### AML/CFT Compliance
- **Transaction records**: 7 years minimum (FATF Recommendation 11)
- **Customer due diligence**: 7 years after business relationship ends
- **Suspicious transaction reports**: 7 years from filing date

### Data Protection (GDPR)
- **Personal data**: As long as necessary for processing purposes
- **Audit logs**: 3 years minimum for compliance demonstration
- **Right to erasure**: Must be able to restore pre-erasure state for legal holds

## Retention Matrix

| Backup Type | Frequency | Retention | Storage Location | Encryption | Purpose |
|-------------|-----------|-----------|------------------|------------|---------|
| **Hourly** | Every 1 hour | 48 hours | Local + S3 | AES-256 | Point-in-time recovery |
| **Daily** | Every 24 hours | 30 days | S3 + Glacier | AES-256 | Recent disaster recovery |
| **Weekly** | Every Sunday | 12 weeks | S3 + Glacier | AES-256 | Weekly snapshots |
| **Monthly** | 1st of month | 12 months | Glacier Deep | AES-256 | Monthly archives |
| **Quarterly** | End of quarter | 7 years | Glacier Deep | AES-256 | Regulatory compliance |
| **Pre-release** | Before deployments | 30 days | S3 | AES-256 | Deployment rollback |

## Storage Tiers

### Hot Storage (Local + S3 Standard)
- **Access time**: Immediate
- **Cost**: $$$
- **Use case**: Recent backups, frequent restores
- **Retention**: 0-48 hours

### Warm Storage (S3 Standard-IA)
- **Access time**: Minutes
- **Cost**: $$
- **Use case**: Recent disaster recovery
- **Retention**: 2 days - 30 days

### Cold Storage (S3 Glacier)
- **Access time**: 3-5 hours
- **Cost**: $
- **Use case**: Weekly/monthly archives
- **Retention**: 30 days - 1 year

### Deep Archive (S3 Glacier Deep Archive)
- **Access time**: 12-48 hours
- **Cost**: ¢
- **Use case**: Regulatory compliance, long-term archives
- **Retention**: 1 year - 7 years

## Backup Schedule

```
┌─────────────┬──────────────┬────────────┬──────────────────┐
│ Time        │ Hourly       │ Daily      │ Weekly/Monthly   │
├─────────────┼──────────────┼────────────┼──────────────────┤
│ 00:00       │ ✓            │ ✓ (Sun)    │ ✓ (1st of month) │
│ 01:00       │ ✓            │            │                  │
│ 02:00       │ ✓            │            │                  │
│ ...         │ ✓            │            │                  │
│ 23:00       │ ✓            │            │                  │
└─────────────┴──────────────┴────────────┴──────────────────┘
```

## Recovery Point Objective (RPO)

| Scenario | RPO | Recovery Method |
|----------|-----|-----------------|
| Accidental data deletion | 1 hour | Restore from hourly backup |
| Application bug | 24 hours | Restore from daily backup |
| Database corruption | 24 hours | Restore from daily backup |
| Data center failure | 24 hours | Restore from S3 daily backup |
| Regional disaster | 7 days | Restore from Glacier weekly backup |
| Regulatory audit | 7 years | Restore from Glacier Deep quarterly backup |

## Recovery Time Objective (RTO)

| Backup Size | RTO | Notes |
|-------------|-----|-------|
| < 1 GB | 5 minutes | Small database |
| 1-10 GB | 15 minutes | Medium database |
| 10-100 GB | 1 hour | Large database |
| > 100 GB | 2-4 hours | Very large database |

## Backup Verification

### Automated Checks
- **Checksum verification**: SHA-256 hash computed on backup creation
- **Restore test**: Weekly automated restore to test database
- **Audit chain verification**: Post-restore audit log integrity check
- **Schema validation**: Alembic migration check after restore

### Manual Tests
- **Monthly**: Full restore drill to staging environment
- **Quarterly**: Disaster recovery simulation
- **Annually**: Full regulatory compliance audit

## Storage Cost Estimates

Assuming 100 GB database size:

| Tier | Monthly Cost | Annual Cost |
|------|--------------|-------------|
| Hourly (48 backups) | $4.80 | $57.60 |
| Daily (30 backups) | $1.50 | $18.00 |
| Weekly (12 backups) | $0.30 | $3.60 |
| Monthly (12 backups) | $0.12 | $1.44 |
| Quarterly (28 backups, 7 years) | $0.07 | $0.84 |
| **Total** | **$6.79** | **$81.48** |

## Implementation

### Backup Script
```bash
# Create backup
./scripts/backup.sh /backups

# Environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=finshield
export DB_USER=finshield
export DB_PASSWORD=secret
export BACKUP_RETENTION_DAYS=30
```

### Restore Script
```bash
# Restore from backup
./scripts/restore.sh /backups/finshield_20261024_120000.sql.gz

# Restore to specific database
./scripts/restore.sh /backups/finshield_20261024_120000.sql.gz finshield_restored
```

### Cron Schedule
```cron
# Hourly backups
0 * * * * /opt/finshield/scripts/backup.sh /backups/hourly

# Daily backups (midnight)
0 0 * * * /opt/finshield/scripts/backup.sh /backups/daily

# Weekly backups (Sunday 1 AM)
0 1 * * 0 /opt/finshield/scripts/backup.sh /backups/weekly

# Monthly backups (1st of month, 2 AM)
0 2 1 * * /opt/finshield/scripts/backup.sh /backups/monthly

# Quarterly backups (end of quarter, 3 AM)
0 3 31 3,6,9,12 * /opt/finshield/scripts/backup.sh /backups/quarterly
```

## Monitoring & Alerting

### Metrics
- `finshield_backup_duration_seconds`: Time to complete backup
- `finshield_backup_size_bytes`: Size of backup file
- `finshield_backup_success_total`: Counter of successful backups
- `finshield_backup_failure_total`: Counter of failed backups

### Alerts
- **Backup failure**: Immediate alert if backup fails
- **Backup size anomaly**: Alert if backup size deviates >50% from average
- **Backup age**: Alert if no successful backup in last 2 hours
- **Storage capacity**: Alert if backup storage >80% full

## Disaster Recovery Plan

### Step 1: Assess Situation
- Determine scope of data loss
- Identify recovery point (how far back to restore)
- Estimate downtime window

### Step 2: Communicate
- Notify stakeholders of incident
- Provide estimated recovery time
- Set up incident bridge call

### Step 3: Restore
1. Stop application servers
2. Identify appropriate backup (based on RPO)
3. Verify backup checksum
4. Restore to new database
5. Run Alembic migrations
6. Verify audit chain integrity

### Step 4: Validate
1. Run application health checks
2. Verify data integrity
3. Test critical user flows
4. Check audit log continuity

### Step 5: Cutover
1. Update DNS/connection strings
2. Start application servers
3. Monitor for errors
4. Verify normal operation

### Step 6: Post-Incident
1. Document timeline
2. Conduct post-mortem
3. Update runbook if needed
4. Schedule follow-up review

## Compliance Notes

- All backups are encrypted at rest (AES-256)
- Backup access is logged and audited
- Quarterly access reviews for backup systems
- Annual penetration testing of backup infrastructure
- Backup encryption keys rotated annually
- Cross-region replication for disaster recovery

## Contact

- **Primary**: DevOps Team (devops@finshield.ai)
- **Secondary**: Security Team (security@finshield.ai)
- **Escalation**: CTO (cto@finshield.ai)

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-24 | FinShield AI | Initial retention matrix |
