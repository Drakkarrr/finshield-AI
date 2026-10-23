# Background worker (S4.1)

Celery with a Redis broker (ruling D2). The worker runs housekeeping only: deliveries, sweeps,
refreshes and checks. **It makes no screening decision.** Screening stays synchronous in the API,
so a worker outage can delay a webhook or a reminder but never changes a decision.

Run it (compose does this as the `worker` service, beat embedded):

    celery -A app.worker.celery_app worker -B --loglevel=INFO

With `APP_ENV=test` tasks run eagerly in-process, so the test suite needs no broker.

## Naming

Task names are `finshield.<domain>.<verb_or_noun>` and are part of the contract: renaming one
orphans messages already queued and breaks the `job_runs` history. Add new names; don't rename.

| Task | Schedule | What it does |
|---|---|---|
| `finshield.webhooks.deliver` | on emit (after commit) | One delivery attempt for one outbox event |
| `finshield.webhooks.outbox_sweep` | every 60 s | Re-enqueues due/stranded outbox events |
| `finshield.audit.seal` | every 60 s | Hash-chains new audit rows (single writer) |
| `finshield.cases.sla_sweep` | every 5 min | Escalates breached cases, warns on approaching ones |
| `finshield.audit.verify` | hourly | Verifies every tenant's chain; increments `audit_chain_breaks_total` |
| `finshield.behavioral.recompute_baselines` | 03:00 | Recomputes account baselines |
| `finshield.lists.refresh` | 04:00 | Re-imports the official OFAC SDN list when it changed (`LISTS_AUTO_DOWNLOAD=true`) |
| `finshield.rag.staleness_check` | 05:00 | Flags RAG tables that are empty or embedded with a different model |
| `finshield.filings.deadline_reminders` | 06:00 | Reminds about filings near their deadline |
| `finshield.privacy.deadline_sweep` | 06:15 | Warns about DSARs near their statutory deadline |
| `finshield.ops.selftest` | manual | Smoke test; `fail=True` exercises the dead-letter path |

## Rules for tasks

- Arguments are ids only, never personal data (they are stored in `job_runs.args` and the broker).
- Idempotent: every task must be safe to run twice (at-least-once delivery).
- Tenant work runs one tenant at a time via `tenant_session(tenant_id)` so RLS applies; only
  cross-tenant discovery uses `system_session()` (explicit RLS bypass).
- Subclass `LedgerTask`: it records each run in `job_runs`, retries up to 3 times with backoff and
  marks the run `dead_letter` when retries are exhausted.

## Dead letters

    python -m scripts.jobs                 # recent dead letters
    python -m scripts.jobs --status all    # every recent run
    python -m scripts.jobs --retry <id>    # re-enqueue a dead-lettered run with its original args

Webhook deliveries that exhaust `webhooks.max_attempts` are dead-lettered on the event itself and
replayed by an admin with `POST /api/v1/webhooks/{event_id}/retry`.
