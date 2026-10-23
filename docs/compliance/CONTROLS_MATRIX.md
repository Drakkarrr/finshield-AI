# FinShield AI — Controls Matrix

Mapping of automated vs procedural controls across regulatory frameworks.

## Control Classification

- **Automated**: Enforced by system code, configuration, or infrastructure
- **Procedural**: Enforced by human processes, policies, or manual review
- **Hybrid**: Combination of automated enforcement with procedural oversight

## Security Controls

| Control ID | Control Name | Type | Implementation | Evidence |
|------------|--------------|------|----------------|----------|
| SEC-001 | Authentication | Automated | JWT tokens with 24h expiry, bcrypt password hashing | `backend/app/auth.py`, `tests/test_auth.py` |
| SEC-002 | Authorization (RBAC) | Automated | Role-based access control with 4 roles (user/analyst/admin/super_admin) | `backend/app/auth.py:require_role()`, `tests/test_rbac.py` |
| SEC-003 | Encryption at Rest | Automated | PostgreSQL TDE, AES-256 for sensitive columns | Infrastructure config, DB schema |
| SEC-004 | Encryption in Transit | Automated | TLS 1.2+ enforced, HSTS headers | `deploy/nginx.conf`, `backend/app/middleware/security.py` |
| SEC-005 | Audit Trail | Automated | Immutable append-only logs with SHA-256 hash chain | `backend/app/db_models.py:AuditLog`, `backend/app/api/audit.py` |
| SEC-006 | Rate Limiting | Automated | SlowAPI with configurable limits per endpoint | `backend/app/main.py:limiter`, `tests/test_rate_limiting.py` |
| SEC-007 | Input Validation | Automated | Pydantic schemas for all API endpoints | `backend/app/models.py`, `backend/app/schemas.py` |
| SEC-008 | Secrets Management | Automated | Environment variables, no hardcoded secrets, `.env` gitignored | `.gitignore`, `.env.example`, `backend/app/config.py` |
| SEC-009 | Multi-Tenancy Isolation | Automated | PostgreSQL RLS, tenant_id on all owned tables | `backend/app/domain/tenancy.py`, `tests/test_tenancy.py` |
| SEC-010 | Session Management | Automated | httpOnly cookies, CSRF tokens, secure flag | `platform-app/src/middleware.ts` |

## Privacy Controls (GDPR)

| Control ID | Control Name | Type | Implementation | Evidence |
|------------|--------------|------|----------------|----------|
| PRIV-001 | Data Subject Access Request (DSAR) | Automated | `/api/v1/privacy/access` endpoint exports all user data | `backend/app/api/privacy.py`, `tests/test_privacy.py` |
| PRIV-002 | Right to Erasure | Automated | `/api/v1/privacy/erasure` endpoint with retention preservation | `backend/app/api/privacy.py`, `tests/test_privacy.py` |
| PRIV-003 | PII Masking | Automated | Audit logs mask email, names, phone, IP addresses | `backend/app/api/audit.py:mask_pii()`, `tests/test_audit.py` |
| PRIV-004 | Data Retention | Hybrid | Automated retention policies (7 years AML, 2 years logs), procedural review | `backend/app/worker/tasks.py:dsar_sweep`, `docs/operations/RETENTION_MATRIX.md` |
| PRIV-005 | Consent Management | Procedural | Privacy policy, terms of service, opt-in for marketing | Legal documents, signup flow |
| PRIV-006 | Data Portability | Automated | CSV/JSON export endpoints for all user data | `backend/app/api/transactions.py:export`, `backend/app/api/privacy.py` |
| PRIV-007 | Breach Notification | Procedural | 72-hour notification process, incident response plan | `docs/operations/INCIDENT_RESPONSE.md` |

## AML/CFT Controls

| Control ID | Control Name | Type | Implementation | Evidence |
|------------|--------------|------|----------------|----------|
| AML-001 | Transaction Monitoring | Automated | 7-stage compliance pipeline with rule engine, behavioral analysis, ML | `backend/app/compliance_engine.py`, `tests/test_compliance.py` |
| AML-002 | Sanctions Screening | Automated | OFAC SDN list matching with fuzzy matching (difflib) | `backend/app/domain/lists.py`, `backend/app/db_models.py:SanctionsEntry` |
| AML-003 | PEP Screening | Automated | Politically Exposed Persons list checking | `backend/app/domain/lists.py`, `tests/test_sanctions.py` |
| AML-004 | Risk Scoring | Automated | Deterministic explainable scoring (no randomness) | `backend/app/compliance_engine.py:_compute_risk()`, `tests/test_scoring.py` |
| AML-005 | Case Management | Automated | Case creation, assignment, status transitions, audit trail | `backend/app/api/cases.py`, `tests/test_cases.py` |
| AML-006 | Filing Generation | Hybrid | Automated SAR/CTR generation templates, procedural review and submission | `backend/app/api/filings.py`, `docs/compliance/FILING_PROCEDURES.md` |
| AML-007 | Record Keeping | Automated | 7-year retention for all transactions and decisions | `backend/app/db_models.py`, `docs/operations/RETENTION_MATRIX.md` |
| AML-008 | Threshold Reporting | Automated | Automatic CTR filing for transactions >$10,000 | `backend/app/compliance_engine.py`, `backend/app/worker/tasks.py:filing_reminders` |
| AML-009 | Suspicious Activity Detection | Automated | Behavioral anomaly detection, ML classification | `backend/app/domain/behavioral.py`, `backend/app/compliance_engine.py` |
| AML-010 | Independent Testing | Procedural | Annual third-party audit, quarterly internal review | Audit reports, test results |

## Operational Controls

| Control ID | Control Name | Type | Implementation | Evidence |
|------------|--------------|------|----------------|----------|
| OPS-001 | Backup and Recovery | Automated | Daily backups with SHA-256 checksums, tested restore procedures | `scripts/backup.sh`, `scripts/restore.sh`, `docs/operations/BACKUP_RESTORE_RUNBOOK.md` |
| OPS-002 | Monitoring and Alerting | Automated | Prometheus metrics, OpenTelemetry tracing, 4 alert rules | `backend/app/observability.py`, `docs/operations/MONITORING.md` |
| OPS-003 | Incident Response | Procedural | On-call rotation, escalation procedures, post-mortem process | `docs/operations/INCIDENT_RESPONSE.md` |
| OPS-004 | Change Management | Procedural | PR review, CI/CD gates, rollback procedures | `.github/workflows/ci.yml`, `docs/development/DEVELOPMENT.md` |
| OPS-005 | Business Continuity | Hybrid | Multi-AZ deployment, RPO<1h, RTO<4h, procedural DR tests | `docs/operations/BCP.md`, DR test results |
| OPS-006 | Vendor Management | Procedural | Third-party risk assessments, SLA monitoring | Vendor register, assessment reports |

## Evidence Collection

### Automated Evidence

Automated controls generate evidence continuously:
- **Audit logs**: Every action logged with timestamp, actor, before/after state
- **Metrics**: Prometheus metrics exported to `/api/metrics`
- **Test results**: CI/CD pipeline runs tests on every commit
- **Backup logs**: Backup success/failure logged with checksums

### Procedural Evidence

Procedural controls require manual evidence collection:
- **Policy documents**: Stored in `docs/policies/`
- **Training records**: Employee training completion tracked in HR system
- **Audit reports**: Third-party audit reports stored securely
- **Incident reports**: Post-mortem documents in `docs/incidents/`

## Control Testing

### Automated Control Testing

```bash
# Run all compliance-related tests
cd backend
APP_ENV=test pytest tests/ -k "audit or privacy or rbac or tenancy or sanctions" -v

# Expected: All tests pass
```

### Procedural Control Testing

- **Quarterly**: Review access logs, verify RBAC enforcement
- **Semi-annually**: Test backup restore, review incident response
- **Annually**: Third-party audit, policy review, training refresh

## Gap Analysis

### Current Gaps

1. **Real-time monitoring dashboard** — Currently metrics are exported but not visualized in real-time
2. **Automated policy enforcement** — Some policies rely on manual review
3. **Customer-facing compliance reports** — No self-service compliance portal

### Remediation Plan

| Gap | Priority | Target Date | Owner |
|-----|----------|-------------|-------|
| Real-time dashboard | Medium | 2027-Q1 | Engineering |
| Automated policy enforcement | High | 2026-Q4 | Engineering |
| Compliance portal | Low | 2027-Q2 | Product |

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-10-24 | 1.0 | Initial controls matrix | Compliance Team |
