# Security and AML due-diligence questionnaire

These are answers to questions of the kind found in SIG-lite, CAIQ and bank vendor-onboarding
questionnaires. The answers are written for this repository at commit `0affe29`.

The answers mean:
- **Yes**: the control exists, and a test, a runbook section or a commit proves it.
- **Partial**: some of it exists, and the gap is stated.
- **No**: it does not exist.

No answer claims a certification. "Cx" refers to the row in [controls-matrix.md](./controls-matrix.md).
Not legal advice.

Summary: **41 questions. 14 Yes, 16 Partial, 11 No.**

## A. Assurance and governance

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| A1 | Do you hold a SOC 2 Type I/II report, ISO 27001 certificate or PCI DSS attestation? | **No** | None has been obtained or started. FinShield stores no cardholder data (see C3), which narrows PCI scope, but there is no attestation. |
| A2 | Has an independent penetration test been performed in the last 12 months? | **No** | None has been performed. The automated security tests are listed in C-01 to C-05 and C-16. They do not replace a pen test. |
| A3 | Do you maintain documented information-security policies (acceptable use, access control, data classification) with an owner and review cycle? | **No** | No policy documents exist. The PII field classification is configuration (`privacy.pii_fields`), not a policy: [test_privacy.py](../../backend/tests/test_privacy.py)`::test_pii_classification_comes_from_config`. |

## B. Identity and access management

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| B1 | Is access controlled by role, with least privilege enforced on every API route? | **Yes** | Four roles and one permission matrix, checked on every protected route (C-01). [test_tenancy_rbac.py](../../backend/tests/test_tenancy_rbac.py)`::test_permission_matrix_for_every_route_and_role`, `::test_analyst_blocked_from_admin_routes_but_can_work_cases`, `::test_only_supervisors_submit_filings`. |
| B2 | Is multi-factor authentication supported or enforced? | **No** | Not implemented. Users log in with a password only. |
| B3 | Is SSO (SAML 2.0 / OIDC) supported? | **No** | Not implemented. The Enterprise plan text in [config_service.py](../../backend/app/config_service.py) lists "SSO + audit export". The audit export exists; SSO does not. |
| B4 | Are passwords stored with a strong one-way hash, with a strength policy and brute-force protection? | **Partial** | Passwords are hashed with bcrypt ([auth.py](../../backend/app/auth.py)). Wrong passwords are rejected: [test_api.py](../../backend/tests/test_api.py)`::TestAuthEndpoints::test_login_wrong_password`. Rate limits are 10 logins/min and 5 registrations/min per IP. Gaps: 8 characters minimum at signup but only 6 on change, no complexity rule, no lockout, failed logins not audited. The rate limits have no test (they are off under `APP_ENV=test`) and are counted in memory per process. |
| B5 | Do sessions expire, and can they be revoked? | **Partial** | The session cookie is httpOnly, Secure and SameSite=Lax, with a CSRF header check and a fixed 24h expiry: [test_session.py](../../backend/tests/test_session.py)`::test_cookie_attributes`, `::test_cookie_authenticated_writes_need_the_csrf_header`, `::test_logout_clears_the_session`. There is no server-side revocation. Logout clears the cookie only; the JWT stays valid until it expires, even after a password change. There is no idle timeout. |
| B6 | Are API credentials stored hashed, and can they be revoked? | **Partial** | API keys are stored hashed: bcrypt, plus a SHA-256 digest used for lookup. Only a prefix is shown ([auth.py](../../backend/app/auth.py)). Unknown keys are rejected: [test_api.py](../../backend/tests/test_api.py)`::TestTransactionScreening::test_invalid_api_key_rejected`, `::TestTransactionScreening::test_api_key_authenticates_requests`. Revocation sets `is_active=false`, and the lookup only accepts active keys. A revoked key is rejected: [test_api_keys.py](../../backend/tests/test_api_keys.py)`::test_revoked_key_is_rejected`. **Partial because** keys have no scopes and no expiry. |
| B7 | Are user access rights reviewed periodically, with a documented joiner/mover/leaver process? | **No** | No review process exists. Admins can list users, change roles and deactivate accounts (`/api/v1/admin/users`), and the tenant always keeps one admin: [test_tenancy_rbac.py](../../backend/tests/test_tenancy_rbac.py)`::test_me_reports_role_and_last_admin_is_protected`. |

## C. Data protection

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| C1 | Is each customer's data logically segregated from other customers'? | **Yes** | `tenant_id` on every owned table, Postgres row-level security, and an application filter (C-02). [test_tenancy_rbac.py](../../backend/tests/test_tenancy_rbac.py)`::test_cross_tenant_reads_are_404_not_403`, `::test_rls_hides_rows_even_when_the_app_filter_is_forgotten` (PG), `::test_rls_survives_a_rolled_back_session_on_a_pooled_connection` (PG). Commit `1481121` fixed a real RLS bypass that the restore drill found. Sanctions lists and model versions are shared by all tenants. |
| C2 | Is data encrypted in transit (TLS 1.2+, HSTS)? | **Partial** | HSTS and the other security headers are sent (commit `fc3d05b`, manual spot check in the [README](./README.md#what-was-re-run-for-this-pack-2026-10-24)). TLS is terminated outside the app, by the optional Caddy profile ([Caddyfile](../../deploy/caddy/Caddyfile)) or the hosting platform. The API itself listens on plain http. The Postgres connection does not require TLS. No TLS scan has been run, and no header test exists. |
| C3 | Is cardholder data kept out of your systems? | **Yes** | Payment is taken on a Stripe-hosted Checkout page. No card column exists: [test_payments.py](../../backend/tests/test_payments.py)`::test_no_card_columns_exist_anywhere`, [test_secrets.py](../../backend/tests/test_secrets.py)`::test_saved_card_endpoints_are_gone`, migration 0008 (commit `8fff080`). |
| C4 | Is data encrypted at rest? | **Partial** | DSAR subject and outcome, and webhook secrets, are encrypted with Fernet at column level: [test_privacy.py](../../backend/tests/test_privacy.py)`::test_erasure_removes_what_it_may_and_retains_what_it_must` asserts the subject is not stored in clear. Transactions, party names, cases and filings are **not** encrypted by FinShield. Disk, volume and backup encryption depend on the host or the S3 bucket. |
| C5 | Are encryption keys managed in a KMS/HSM and rotated? | **No** | One environment secret, `DATA_ENCRYPTION_KEY`, derives every key through HKDF ([crypto.py](../../backend/app/crypto.py)). There is no KMS or HSM and no rotation procedure. Key custody is procedural: [retention.md](./retention.md#procedures), "Encryption keys". |
| C6 | Are secrets kept out of code and images, and required at startup? | **Partial** | The API refuses to start without `JWT_SECRET_KEY` (at least 32 characters) or `DATA_ENCRYPTION_KEY`: [test_secrets.py](../../backend/tests/test_secrets.py)`::test_api_refuses_to_start_without_jwt_secret`, `::test_api_refuses_to_start_without_data_encryption_key`. CI runs gitleaks on the tree. Gaps: git history still contains a formerly tracked `backend/.env` (removed in `fa26839`, history not rewritten), and there is no vault. |
| C7 | Is personal data minimised in logs, audit entries and outbound events, and masked for lower-privilege users? | **Yes** | Audit entries hold HMAC pseudonyms, not names: [test_audit.py](../../backend/tests/test_audit.py)`::test_screening_decision_is_audited_with_model_version_and_no_raw_names`. Webhook payloads carry ids only: [test_operations.py](../../backend/tests/test_operations.py)`::test_healthy_subscriber_gets_a_payload_whose_hmac_verifies`. Analysts see masked names and account ids in lists, detail, CSV export and search: [test_privacy.py](../../backend/tests/test_privacy.py)`::test_masked_role_cannot_read_unmasked_names_or_accounts`. Sentry runs with `send_default_pii=False`. |
| C8 | Can the customer choose where data is stored (data residency)? | **Partial** | There is no hosted FinShield service yet. The compose stack runs wherever the deployer puts it, so residency is the deployer's choice. No hosted region, residency commitment or data processing agreement exists. |
| C9 | Do you publish a list of subprocessors? | **Partial** | No formal list or DPA exists. From the code, the only third parties are optional and switched on by configuration: Stripe (`PAYMENTS_MODE=stripe`), Sentry (`SENTRY_DSN`), an OTLP trace collector (`OTEL_EXPORTER_OTLP_ENDPOINT`) and an S3 bucket for backups (`BACKUP_S3_URI`). The OFAC list is downloaded from the US Treasury, which is a data source, not a processor. No email provider is integrated. |

## D. Logging and monitoring

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| D1 | Are security-relevant events logged (logins, privilege changes, configuration changes, data exports)? | **Partial** | Audited: screening decisions, logins, registration, password changes, user creation and role changes, setting, flag and rule changes (before and after), model registration and promotion, breaker resets, filing create/update/delete, DSARs, audit exports, webhook changes. Evidence: [test_settings.py](../../backend/tests/test_settings.py)`::test_threshold_change_takes_effect_without_restart_and_is_audited`, `::test_rule_update_bumps_version_and_audits_before_after`. **Not audited:** failed logins, API key creation and revocation, deletion of transactions and cases, reads. `ip_address` is never filled in. |
| D2 | Is the audit log tamper-evident and exportable in a form a third party can verify? | **Yes** | Each tenant has a hash chain. A Postgres trigger makes the table append-only, and the export is signed with Ed25519 (C-05). [test_audit.py](../../backend/tests/test_audit.py)`::test_tampering_breaks_verification_and_the_export_reports_it`, `::test_export_verifies_independently`, `::test_update_and_delete_fail_at_the_database_level` (PG). The standalone verifier is [verify_audit_export.py](../../backend/scripts/verify_audit_export.py). Limitation: the signing key comes from the server's own secret, and the head hash is not anchored outside the system. |
| D3 | How long are logs retained? | **Partial** | The audit trail is kept indefinitely; the trigger blocks DELETE and TRUNCATE ([retention.md](./retention.md)). Application logs go to stdout as JSON, and their retention depends on the platform; it is not defined. |
| D4 | Is the service monitored, with alerts routed to an on-call person? | **Partial** | Health probes, Prometheus metrics and 8 alert rules exist (C-12): [test_api.py](../../backend/tests/test_api.py)`::TestS04HealthProbes::test_ready_and_health_503_when_db_unreachable`, [test_operations.py](../../backend/tests/test_operations.py)`::test_metrics_endpoint_requires_its_token`, [alerts.yml](../../deploy/prometheus/alerts.yml) (promtool OK, commit `cdd5c65`). No Prometheus, Alertmanager, paging or on-call rotation is deployed. |

## E. Privacy and records management

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| E1 | Can you fulfil data-subject access and erasure requests? | **Yes** | DSAR requests carry a 30-day due date, an access export and a retention-aware erasure (C-06). [test_privacy.py](../../backend/tests/test_privacy.py)`::test_access_export_is_complete_and_withholds_filings`, `::test_erasure_removes_what_it_may_and_retains_what_it_must`. A supervisor executes each request; that step is procedural. |
| E2 | Is there a retention schedule, and is it enforced? | **Partial** | The schedule, with legal bases, is in [retention.md](./retention.md). Erasure refuses records inside the 5-year window or linked to a case or filing (test above). Gaps: a supervisor can **hard-delete** a transaction or case through the API with no retention check and no audit entry. There is no automated purge after the window ends. |
| E3 | Do you have a personal-data breach notification procedure (e.g. GDPR 72 hours)? | **No** | No procedure or contact path is documented. |

## F. Resilience and continuity

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| F1 | Are backups taken regularly and kept for a defined period? | **Yes** | [backup.sh](../../scripts/backup.sh) runs daily in the compose `backup` service: checksummed, checked for readability, kept 35 days with the newest 7 always kept, optional S3 copy. Runbook: [DEPLOYMENT.md, Phase 9](../../DEPLOYMENT.md#phase-9-backup-and-restore--implemented-s45). Commit `b24b374`. The off-host copy is optional, and backup encryption depends on the bucket. |
| F2 | Has a restore from backup been tested? | **Yes** | One drill, on 2026-10-23: backup, drop the source, restore into a fresh cluster. It produced the same audit head hash, and the standalone verifier passed. The transcript is in [DEPLOYMENT.md, Phase 9](../../DEPLOYMENT.md#phase-9-backup-and-restore--implemented-s45). No recurring drill is scheduled, and none runs in CI. |
| F3 | Are RTO and RPO defined and tested? Is there an HA/DR or business-continuity plan? | **No** | RTO and RPO are not defined. The RPO is in effect the backup interval (24h by default), since there is no point-in-time recovery. The drill did not measure RTO. Every component is a single instance, and there is no BCP. |
| F4 | Does the service fail safe when a dependency is unavailable? | **Yes** | A degraded decision is held for review and never auto-approved (C-11). [test_detection.py](../../backend/tests/test_detection.py)`::test_dead_rag_routes_to_review_opens_breaker_then_recovers`, `::TestLists::test_missing_list_is_degraded_never_approved`. Exception: a *stale* sanctions list does not degrade decisions (see H1). |

## G. Incident, vulnerability and change management

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| G1 | Do you have a documented, tested incident response plan? | **No** | None exists. The only incident guidance is the annotation on the `AuditChainBroken` alert in [alerts.yml](../../deploy/prometheus/alerts.yml): "treat as a security incident". |
| G2 | Do you scan dependencies for known vulnerabilities, and block releases on findings? | **Yes** | The CI job `security-scan` runs `pip-audit`, `npm audit --audit-level=high` and gitleaks, all blocking ([ci.yml](../../.github/workflows/ci.yml)). Commit `5fd6c23` cleared all 21 pip-audit findings. There is no SAST and no container image scan. |
| G3 | Are changes controlled (review, automated tests, migration checks, rollback)? | **Partial** | CI runs lint, types, the test suite with an 84% coverage floor, the suite on Postgres and an Alembic up/down/up ([ci.yml](../../.github/workflows/ci.yml)). Tests: [test_routes.py](../../backend/tests/test_routes.py)`::test_openapi_matches_snapshot`, [test_migrations.py](../../backend/tests/test_migrations.py)`::test_migrations_match_models` (PG). Runtime config changes are versioned and audited (D1). There is no evidence of branch protection or mandatory code review, and releases are not tagged. |
| G4 | Do production containers run as non-root, from minimal images? | **Yes** | The backend image is multi-stage, runs as uid 10001 and contains no compiler (commit `b6120d4`, checked in the built image). Base images are pinned by tag, not digest. |

## H. AML-specific

| # | Question | Answer | Evidence and notes |
|---|---|---|---|
| H1 | Which sanctions lists do you screen against, and how is list freshness assured? | **Partial** | **OFAC SDN only**, from the official export with aliases. Every hit records the list version: [test_detection.py](../../backend/tests/test_detection.py)`::TestLists::test_alias_hit_names_entry_version_and_score`. The list is refreshed daily when `LISTS_AUTO_DOWNLOAD=true`. A stale list (older than 48h) makes `/api/health` return 503 and fires `SanctionsListStale`, but screening goes on against the stale list without degrading. There are no UN, EU, UK or local lists. |
| H2 | Do you screen against PEP lists? | **Partial** | PEP matching works (RULE-002, flag): [test_compliance_engine.py](../../backend/tests/test_compliance_engine.py)`::TestRuleEngine::test_pep_match_triggers`. **The only PEP data shipped is a fictional fixture.** A licensed PEP source must be imported with `scripts.import_lists pep`. Compose loads the fictional fixture by default (`LISTS_DEMO_FIXTURES=true`). |
| H3 | Are decisions explainable and reproducible for an examiner? | **Yes** | The decision path is deterministic and stores reasons, rule results, model version and list versions. A replay returns the stored decision (C-09). [test_detection.py](../../backend/tests/test_detection.py)`::TestDeterminism::test_same_payload_twenty_times_identical`, `::TestDeterminism::test_every_non_approved_decision_has_reasons`, `::test_api_decisions_are_persisted_and_reproducible`, `::test_replay_returns_the_stored_decision`. |
| H4 | Are models governed: versioned, validated, approved, and monitored for drift? | **Partial** | Versioning, shadow scoring and audited promotion exist: [test_detection.py](../../backend/tests/test_detection.py)`::test_shadow_scored_and_stored_but_never_decides_then_promotion_does`. A nightly eval gate runs over 51 synthetic scenarios, and a `ClassifierDrift` alert rule exists. Gaps: the model card's approval is "pending review", the weights are expert-set rather than trained, and the risk model alone has recall 0.0 on the eval set ([baseline.json](../../backend/tests/eval/baseline.json)). There is no independent validation and no four-eyes promotion. |
| H5 | Is the subject of a SAR protected from tipping-off in data-subject requests? | **Yes** | The access export withholds cases, notes and filings and records the legal basis (31 U.S.C. 5318(g)(2); GDPR Art. 23): [test_privacy.py](../../backend/tests/test_privacy.py)`::test_access_export_is_complete_and_withholds_filings`. Not legal advice. |
| H6 | Does the product file SARs/STRs directly with the regulator (e.g. FinCEN BSA E-Filing, goAML)? | **No** | FinShield drafts filings, tracks their deadlines and records submitted and confirmed status, with supervisor approval. The customer submits to the regulator outside FinShield. A narrative can still be edited after it is marked submitted. |
| H7 | Are outbound event notifications authenticated and protected against SSRF? | **Yes** | Each webhook is signed with HMAC-SHA256 over a timestamp and the body. An SSRF guard runs at subscribe time and at delivery. Retries back off, then go to a dead-letter queue (C-16). [test_operations.py](../../backend/tests/test_operations.py)`::test_healthy_subscriber_gets_a_payload_whose_hmac_verifies`, `::test_ssrf_guard_rejects_private_targets_by_default`, `::test_failing_subscriber_is_retried_with_backoff_then_dead_lettered_and_replayable`. |

## Questions this pack cannot answer

These depend on an operator or organisation that does not exist yet. Answer them when a production
deployment and an owner exist:

- Hosting provider, region, physical security
- Uptime SLA history
- Staff background checks
- Security training
- Cyber insurance
- Vendor-risk programme for FinShield's own suppliers
- Named security and DPO contacts
