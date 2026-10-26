# Limitations and target state

These are the gaps a bank's vendor-risk team, an auditor or an AML examiner would raise about
FinShield, written for commit `0affe29`. Priorities:
- **P1**: would block a regulated customer, or is a record-keeping or control failure.
- **P2**: will be asked about, and needs a plan with a date.
- **P3**: worth knowing.

Each item names the code or the missing artefact, and what would close it. Not legal advice.

## P1

| # | Gap | Why it matters | What closes it |
|---|---|---|---|
| ~~L1~~ | ~~**Supervisors can hard-delete screened transactions and cases.**~~ **CLOSED (S7.1):** Delete endpoints now refuse inside the retention window and for anything linked to a case or filing. Transactions outside the window are pseudonymised instead of hard-deleted. Every delete attempt is audit-logged. | AML record-keeping (e.g. 31 CFR 1010.430) needs these records kept for 5 years. A deletion that leaves no trace undermines both the retention matrix and the audit trail. | ~~Refuse deletion inside the retention window and for anything linked to a case or filing, with the same rules as DSAR erasure. Audit every delete. Or remove the endpoints and pseudonymise through the erasure path.~~ **Done.** |
| L2 | **Sanctions and PEP coverage.** Only OFAC SDN is imported. UN, EU, UK (OFSI) and local lists are missing. The only PEP data shipped is a **fictional fixture**, and compose loads it by default (`LISTS_DEMO_FIXTURES=true`). A *stale* list makes `/api/health` return 503 and fires an alert, but decisions are **not** degraded; only a *missing* list degrades them. The readiness-probe docstring in [health.py](../../backend/app/api/health.py) says otherwise. | A screening vendor's list coverage is the first AML due-diligence question. Fictional PEP data in production would make every PEP check meaningless. | Add importers for the lists the customer's jurisdiction requires, and a licensed PEP feed. Default `LISTS_DEMO_FIXTURES` to false outside development. Treat a stale sanctions list as a degraded dependency. Add a test for the stale-list path. |
| L3 | **No MFA, no SSO, no session revocation, no lockout.** Login uses a password and a 24h JWT. Logout and password changes don't invalidate tokens. Failed logins are not audited. The password minimum is 8 characters at signup and 6 on change. | MFA for privileged access to customer financial data is a near-universal requirement in bank questionnaires. | Add TOTP/WebAuthn MFA (required for supervisor and admin), and OIDC/SAML SSO for enterprise tenants. Add a token version or deny-list so logout and password changes revoke tokens. Add a lockout with audited failures, and one password policy. |
| L4 | **Model and rule governance are single-actor and unvalidated.** The v1 model card's `approval` is "pending review" ([registry.py](../../backend/app/domain/models_registry/registry.py)). The weights are expert-set, not trained, and the model alone has recall 0.0 on the eval set ([baseline.json](../../backend/tests/eval/baseline.json)). The 51 scenarios are synthetic. One admin can promote a model, or **disable the sanctions rule RULE-001 indefinitely**; this is audited but nothing stops it. | Model-risk guidance expects documented validation, independent review and segregation of duties for changes to detection logic. | Get a named approver to sign off the model card. Validate the model independently on labelled outcomes. Require a second approver for model promotion and rule disable. Refuse to disable RULE-001 at all. |
| L5 | **No incident response or breach-notification process, and alerting is not deployed.** [alerts.yml](../../deploy/prometheus/alerts.yml) has 8 rules, but compose runs no Prometheus or Alertmanager, and no on-call exists. | An audit-chain break or a data leak would go unnoticed outside the in-app notification, and nobody is named to act on it. Regulators and GDPR (Art. 33) expect a notification capability. | Write an incident response plan (roles, severity, customer and regulator notification, evidence preservation, post-mortem) and test it with a tabletop exercise. Deploy the monitoring stack and route the critical alerts to a pager. |
| L6 | **Key management.** One environment secret, `DATA_ENCRYPTION_KEY`, derives the column-encryption key, the pseudonym key and the audit-signing key ([crypto.py](../../backend/app/crypto.py)). There is no KMS or HSM and no rotation, and rotating the key would break old exports and pseudonym links. Because the signing key lives with the server, someone with superuser rights **and** the key could rewrite the audit chain and re-sign it. Nothing anchors the head hash outside the system. | Examiners treat the audit trail as evidence. Its tamper-evidence should not depend on the same secret an attacker with full server access already holds. | Move key material to a KMS, sign with a KMS-held key, and write a rotation procedure with versioned keys. Publish the chain heads somewhere outside the database on a schedule (customer webhook, object-lock bucket, or an RFC 3161 timestamp). |
| L7 | **Core personal data is not encrypted at rest by FinShield.** Party names, account ids, case notes and SAR narratives are plaintext columns. Backups contain them in clear. | Questionnaires ask for encryption at rest, and the only true answer today is "depends on your host". | Require encrypted storage in the deployment guide (managed Postgres with encryption at rest, an encrypted volume, an SSE-KMS bucket for backups). Consider column encryption for SAR narratives. |
| L8 | **No RTO/RPO, no HA, one restore drill.** Every component is a single instance. There is no point-in-time recovery, so the RPO is the backup interval (24h by default). Restore was drilled once (2026-10-23) and its duration was not measured. | Banks will ask for contractual RTO/RPO and evidence of periodic DR tests. | Set targets. Enable managed PITR. Schedule a quarterly restore drill, or an automated one in CI, that records how long it took. Document failover. |

## P2

| # | Gap | What closes it |
|---|---|---|
| L9 | **Audit coverage.** Not audited: failed logins, API key creation and revocation, transaction and case deletion (L1), data reads. `audit_logs.ip_address` is never filled in. | Audit these events, and record the client IP when it is behind a trusted proxy. |
| L10 | **No third-party assurance or policies.** No pen test, no SOC 2 or ISO 27001, no security policies, no vendor-risk programme. Git history still holds the formerly tracked `backend/.env`; rewriting history is a pending decision ([PROGRESS.md](../architecture/evolution/PROGRESS.md)). | Commission a pen test before the first regulated customer. Write a minimal policy set. Decide on the history rewrite and rotate any secret that was in that file. |
| L11 | **Change control is technical only.** CI gates exist, but there is no evidence of branch protection, mandatory review or tagged releases. Much of the code was written by AI agents. | Turn on branch protection with required reviews and required CI checks. Tag releases. Keep the slice ledger as the change record. |
| L12 | **Filings.** Every tenant role, analyst included, can read filings. A narrative stays editable after `submitted`. There is no direct e-filing to FinCEN or goAML; the customer submits outside FinShield. | Restrict filing reads to investigator and above. Lock the narrative on submission, with any amendment as a new audited version. State clearly that FinShield does not file on the customer's behalf. |
| L13 | **Retention is enforced only on the erasure path.** There is no automated purge after the window ends. Erasures are not re-applied automatically after a restore, and no erasure log is kept outside the database ([retention.md](./retention.md)). There is one global 5-year setting, not one per jurisdiction. | Add a reviewed purge job, an erasure ledger outside the database, and retention per tenant or per jurisdiction. |
| L14 | **Transport and perimeter.** TLS terminates outside the app, and no TLS scan has been run. No automated test covers the security headers. The Postgres connection does not require TLS. Base images are pinned by tag, not digest. There is no SAST and no image scan. Rate limits are kept in memory per process, and no test covers them. | Add a header test. Use `sslmode=require` on managed databases. Pin images by digest and add image and SAST scanning. Move rate limits to Redis and test them. |
| L15 | **Payments default to simulated.** `PAYMENTS_MODE` defaults to `simulated`, which grants credits without payment. Only credit packs exist (no subscriptions, refunds or dunning), and nothing has run against a real Stripe test-mode key. | Fail startup in production unless `PAYMENTS_MODE=stripe`. Finish the billing scope. |
| L16 | **Claims ahead of the code.** The Enterprise plan text in [config_service.py](../../backend/app/config_service.py) lists "SSO", "On-premise / VPC" and "99.9% uptime SLA", none of which exist. DEPLOYMENT.md Phases 7, 8, 10 and 11 are marked PROPOSED and partly out of date (Neon, PayMongo, an old header snippet). The [permissions.py](../../backend/app/permissions.py) docstring names a test file that does not exist. | Remove or relabel the plan features. Bring DEPLOYMENT.md in line with S4.5 and S6.2. Fix the docstring. |

## P3

| # | Gap | Note |
|---|---|---|
| L17 | Name matching is Latin-script only (accents folded, no transliteration). | Matters for Cyrillic, Arabic and CJK names on sanctions lists. |
| L18 | Decisions depend on account history (velocity, behavioural baseline). The same payload can give a different result later, so an old decision has to be read from storage, not recomputed. | This is by design, and the stored decision is the record. |
| L19 | Reference data is shared by all tenants (watchlists, high-risk countries, model versions, circuit breakers, RAG corpora). Auth lookup and system jobs use a narrow RLS bypass. | Acceptable for shared reference data. A customer needing physical separation would need a dedicated deployment, which is not offered. |
| L20 | API keys inherit the creating user's full role, with no scopes and no expiry. | Add scopes and expiry. |

## What is solid today

These controls have direct, passing test evidence (see [controls-matrix.md](./controls-matrix.md)):
- RBAC on every route
- Tenant isolation, including RLS
- An append-only, hash-chained audit trail with an independently verifiable signed export
- DSAR handling that keeps what the law requires and withholds SAR material
- Deterministic, explained decisions
- A pipeline that never auto-approves when degraded
- Signed, SSRF-guarded webhooks
- Stripe payments with no card data stored
- A restore drill that proved the audit chain survives backup and restore
