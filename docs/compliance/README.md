# FinShield compliance evidence pack

Slice S6.6. Written 2026-10-24 against branch `claude/backend` at commit `5bbf592`. That commit
merged main, and its own S3.2/S3.3 superseded the parallel Qoder S3.2/S3.3. The backend at
`5bbf592` matches `0493af3`, apart from one change to the case-status list in `api/cases.py`.

This pack describes the controls that exist in this repository and links each one to its evidence: a
test, a runbook section, or a commit. If a control has none of these, the pack says so. It is
**not legal advice**, and it is **not a certification**. FinShield holds no SOC 2, ISO 27001 or PCI DSS
attestation, and has not had a penetration test.

## Documents

| Document | What it answers |
|---|---|
| [controls-matrix.md](./controls-matrix.md) | One row per control: how it is built, whether it is automated or procedural, the evidence, and known gaps. |
| [questionnaire.md](./questionnaire.md) | Answers to 41 typical vendor security and AML due-diligence questions (SIG-lite / CAIQ style), each with an evidence link. |
| [limitations.md](./limitations.md) | The gaps a bank, auditor or regulator would flag, in priority order. |
| [retention.md](./retention.md) | Retention period and legal basis for each data class, and how each one is enforced (S4.5). |

Other evidence that lives outside this folder:

- Backup and restore runbook with a real drill transcript: [DEPLOYMENT.md, Phase 9](../../DEPLOYMENT.md#phase-9-backup-and-restore--implemented-s45)
- Alert rules: [deploy/prometheus/alerts.yml](../../deploy/prometheus/alerts.yml)
- CI pipeline: [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- Model card (built-in risk model v1): `V1_MODEL_CARD` in [registry.py](../../backend/app/domain/models_registry/registry.py). Registered models carry their card in `model_versions.model_card`, served by `GET /api/v1/models`.
- Evaluation harness and baseline metrics: [run_eval.py](../../backend/tests/eval/run_eval.py), [baseline.json](../../backend/tests/eval/baseline.json)
- Slice ledger with the evidence for each slice: [PROGRESS.md](../architecture/evolution/PROGRESS.md)

## Scope

In scope:
- The FastAPI backend (`backend/app`)
- Its Postgres schema and migrations (`backend/migrations`)
- The Celery worker (`backend/app/worker`)
- The backup and restore scripts (`scripts/`)
- The compose deployment and the optional Caddy TLS proxy (`deploy/caddy`)
- The CI pipeline

Out of scope:
- The Next.js web app (`platform-app/`). Another track builds it; this pack makes no claims about it beyond the session cookie the backend sets.
- Any hosting provider. There is no production deployment yet, so nothing is said about a data centre, its physical security or its availability.
- The customer's own AML programme: KYC/CDD, the decision to file, and actual submission to a regulator.

## Status: automated, procedural, not implemented

**Automated** means code enforces the control and a test in `backend/tests/` proves it. **Procedural**
means a person has to do something by following a runbook. **Not implemented** means nothing exists.

| Automated (enforced by code, proven by a test) | Procedural (runbook, needs a named owner) | Not implemented |
|---|---|---|
| RBAC on every protected route (4 roles) | Restore from backup (DEPLOYMENT.md Phase 9, drilled once) | MFA, SSO (SAML/OIDC) |
| Tenant isolation: app filter + Postgres RLS | Deleting expired records (retention.md, yearly) | Server-side session revocation, account lockout |
| Append-only, hash-chained audit trail + signed export | Re-applying erasures after a restore | KMS/HSM, key rotation |
| Required secrets checked at startup | Storing and backing up `DATA_ENCRYPTION_KEY` | Incident response plan, breach notification procedure |
| DSAR access export and retention-aware erasure | Executing DSARs (a supervisor runs each request) | Defined RTO/RPO, point-in-time recovery, HA/multi-region |
| Tipping-off protection in DSAR exports | Sanctions list refresh when `LISTS_AUTO_DOWNLOAD` is off | Penetration test, SOC 2 / ISO 27001 |
| PII masking for the analyst role; pseudonyms in audit | Loading a licensed PEP list (only fictional data ships) | UN / EU / UK sanctions lists (OFAC SDN only) |
| Deterministic, explained, replayable decisions | Model approval: the card's `approval` stays "pending review" | Four-eyes approval for model promotion and rule changes |
| Fail-safe degraded mode (never auto-approve) | Running Prometheus/Alertmanager and routing alerts | Periodic access reviews |
| Webhook HMAC signing, SSRF guard, retry/DLQ | TLS termination (Caddy profile or the PaaS) | Off-database erasure log |
| Stripe webhook verification; no card data stored | Daily backups (compose `backup` service; script-enforced retention) | Automated retention purge |
| Security headers on every API response | | Container image scanning, SAST |
| CI gates: lint, types, tests on SQLite and Postgres, dependency and secret scans | | |

## Regenerating the evidence

All commands run from `backend/` unless noted otherwise.

```sh
# Whole backend suite on SQLite (Postgres-only tests are skipped)
APP_ENV=test pytest tests/

# The same suite on Postgres. This adds RLS, the audit trigger and the migration tests.
APP_ENV=test TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/fstest pytest tests/

# Control-specific runs
APP_ENV=test pytest tests/test_tenancy_rbac.py            # RBAC matrix, tenant isolation, RLS
APP_ENV=test pytest tests/test_audit.py                   # audit chain, tamper detection, signed export
APP_ENV=test pytest tests/test_privacy.py                 # DSAR, erasure, masking, tipping-off
APP_ENV=test pytest tests/test_secrets.py tests/test_payments.py tests/test_session.py
APP_ENV=test pytest tests/test_detection.py tests/test_compliance_engine.py   # determinism, degraded mode
APP_ENV=test pytest tests/test_operations.py              # webhooks, SSRF, SLA, metrics, tracing

# Audit chain check across all tenants, against a live database (DATABASE_URL set).
# Prints one head hash per tenant. --export-dir also writes a signed bundle per tenant and public-key.pem.
python -m scripts.audit_check --export-dir /tmp/audit

# Independent verification of an export. Imports no FinShield code. Get the trusted key out of band
# from GET /api/v1/audit/public-key.
python scripts/verify_audit_export.py /tmp/audit/<tenant>.json --public-key trusted.pem

# Evaluation harness: per-stage precision and recall against the baseline. It writes tests/eval/report.json.
APP_ENV=test python -m tests.eval.run_eval

# Alert rules syntax check (repo root, needs promtool)
promtool check rules deploy/prometheus/alerts.yml

# Backup and restore (repo root). See DEPLOYMENT.md Phase 9 for the full procedure.
DATABASE_URL=postgresql://owner@host/db scripts/backup.sh
DATABASE_URL=postgresql://owner@host/empty_db scripts/restore.sh backups/finshield-<ts>.dump
```

### What was re-run for this pack (2026-10-24)

- **SQLite suite: 150 passed, 9 skipped.** Run locally with Python 3.13 and `requirements.txt` plus
  `requirements-dev.txt`. numpy was unpinned because 1.26.4 has no 3.13 wheel; CI and the image use
  Python 3.11. The commit message of `0493af3` records the same count.
- **Security headers, manual spot check.** `GET https://test/api/health/live` through the ASGI test
  client returned `nosniff`, `DENY`, `no-referrer`, the Permissions-Policy, COOP `same-origin`,
  CSP `default-src 'none'; frame-ancestors 'none'`, `Cache-Control: no-store` and HSTS. No automated
  test covers the headers.
- **Postgres-only tests (marked "PG" in the matrix) were not re-run for this pack.** They are:
  - RLS: `test_rls_hides_rows_even_when_the_app_filter_is_forgotten`, `test_rls_survives_a_rolled_back_session_on_a_pooled_connection`
  - Audit trigger: `test_update_and_delete_fail_at_the_database_level`
  - Migrations: `test_database_is_at_alembic_head`, `test_migrations_match_models`

  Their last recorded result is in commit `0493af3`: "Postgres 158 passed / 1 skipped". The CI job
  `backend-postgres` runs them. Re-run them with the Postgres command above before you send this pack out.

## Conventions

- Test evidence is written `backend/tests/<file>.py::<test_name>` and links to the file.
- "PG" marks a test that runs only on Postgres. On SQLite it is skipped.
- A commit hash refers to this repository's history (`git show <hash>`).
- Regulatory citations are limited to the ones already used in the code and in retention.md:
  31 CFR 1010.430, 31 CFR 1020.320, 31 U.S.C. 5318(g)(2), GDPR Art. 5(2), 17(3)(b) and 23. Not legal advice.

## Keeping the pack true

Update the matrix in the same change as the code when any of these happen:
- a control changes
- a test is renamed
- a gap is closed

Check every link in this folder before you send the pack to a customer. A "Yes" whose test no longer
exists becomes a "No".
