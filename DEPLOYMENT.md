# FinShield AI — Production Deployment Guide

> Step-by-step guide to take FinShield from local dev to a live, revenue-generating SaaS.
> Written for a solo developer based in the Philippines.

> **Status: IMPLEMENTED.** The production stack is Docker Compose with Postgres, Stripe for payments (S6.1), and container hardening (S6.3). Security headers, rate limiting, and audit logging are active. For running locally today, follow the [README quick start](./README.md#quick-start).

---

## Prerequisites Checklist

Before starting, make sure you have:

- [ ] A domain name (buy from [Porkbun](https://porkbun.com) or [Namecheap](https://namecheap.com), ~$10/yr)
- [ ] GitHub account with repo access
- [ ] A business registration (DTI for sole prop, or SEC for corporation)
- [ ] BIR registration (for issuing official receipts)
- [ ] Stripe account (sign up at [stripe.com](https://stripe.com))
- [ ] A bank account (for Stripe payouts)
- [ ] Docker Desktop with Compose v2
- [ ] Node.js 18+ and Python 3.11+ on your local machine (for development only)

---

## Phase 1: Database (PostgreSQL) — IMPLEMENTED

The production stack uses Postgres via Docker Compose. The database is initialized with Alembic migrations on startup.

### Setup

1. Ensure `DATABASE_URL` is set in your `.env` file:

```bash
# backend/.env
DATABASE_URL=postgresql://finshield:password@postgres:5432/finshield
```

2. The database is automatically initialized when you run `docker compose up`:
   - Alembic migrations run on startup (`alembic upgrade head`)
   - Tables are created/updated to the latest schema
   - Row-level security policies are applied

3. For manual migration:

```bash
docker compose exec backend alembic upgrade head
```

### Backups

See [Phase 9: Backup and restore](#phase-9-backup-and-restore-implemented-s45) for backup procedures.

---

## Phase 2: Backend Deployment (Railway) — PROPOSED

Railway gives you a free-tier Python server with auto-deploy from GitHub.

### Steps

1. Go to [railway.app](https://railway.app) → Sign up with GitHub
2. Create a new project → Deploy from GitHub repo → Select `finshield` repo
3. Set root directory: `backend/`
4. Railway auto-detects Python. If not, add a `Procfile` in `backend/`:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Set environment variables in Railway dashboard:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | (from Neon) |
| `JWT_SECRET_KEY` | (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `CORS_ORIGINS` | `https://yourdomain.com,https://app.yourdomain.com` |
| `APP_PORT` | (Railway sets `$PORT` automatically) |
| `DEBUG` | `false` |

6. Add `requirements.txt` if not present:

```bash
cd backend
pip freeze > requirements.txt
```

7. Deploy. Railway gives you a URL like `https://finshield-production.up.railway.app`

### Health Check

Visit `https://your-railway-url.com/api/health` — should return `{"status": "healthy"}`.

---

## Phase 3: Frontend Deployment (Vercel) — PROPOSED

### Steps

1. Go to [vercel.com](https://vercel.com) → Sign up with GitHub
2. Import your `finshield` repo
3. Set framework: **Next.js**
4. Set root directory: `platform-app/`
5. Add environment variable:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://your-railway-url.up.railway.app/api` |

6. Update `platform-app/src/lib/api.ts` to use the env var:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';
```

7. Update `platform-app/next.config.js` to proxy API in production:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8091/api'}/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
```

8. Deploy. Vercel gives you `your-project.vercel.app`
9. Connect your custom domain in Vercel settings (add CNAME record at your DNS provider)

---

## Phase 4: Payment Integration (Stripe) — IMPLEMENTED (S6.1)

Stripe Checkout + Stripe Billing handles all payment processing. The backend stores only Stripe customer, subscription, and payment-method IDs (no card data).

### Setup

1. Sign up at [stripe.com](https://stripe.com)
2. Get your API keys from Dashboard → Developers → API keys
3. Set environment variables:

```bash
# backend/.env
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

4. Configure webhook endpoint in Stripe Dashboard:
   - URL: `https://yourdomain.com/api/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`

### Implementation

The payment flow is fully implemented:
- `POST /api/v1/billing/checkout` — creates Stripe Checkout session
- `POST /api/webhooks/stripe` — handles Stripe webhooks (credit updates, subscription changes)
- `GET /api/v1/billing/subscription` — returns current subscription status
- `GET /api/v1/billing/invoices` — returns invoice history

See `backend/app/api/billing.py` for the full implementation.

---

## Phase 5: Email Notifications (Resend) — PROPOSED

### Setup

1. Sign up at [resend.com](https://resend.com) — free tier: 100 emails/day
2. Verify your sending domain (add DNS records)
3. Get your API key

### Implementation

```bash
cd backend
pip install resend
```

Create `backend/app/email.py`:

```python
import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

def send_email(to: str, subject: str, html: str):
    params = {
        "from": "FinShield <notifications@yourdomain.com>",
        "to": [to],
        "subject": subject,
        "html": html,
    }
    resend.send_email(params)
```

Wire into notification creation (e.g., when trial is about to expire):

```python
# In a daily cron job or scheduled task
def check_trial_expiring():
    """Send reminder 3 days before trial expires."""
    soon = datetime.utcnow() + timedelta(days=3)
    users = db.query(User).filter(User.is_trial == True, User.trial_expires_at <= soon)
    for user in users:
        send_email(user.email, "Your trial expires in 3 days", "...")
```

---

## Phase 6: Environment Variables (Complete List)

Create a `.env` file for production (never commit this):

```bash
# backend/.env

# Database
DATABASE_URL=postgresql://finshield:password@postgres:5432/finshield

# Security
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
DATA_ENCRYPTION_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Application
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Optional: Sentry
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx

# Optional: Redis (for Celery workers)
REDIS_URL=redis://redis:6379/0
```

---

## Phase 7: Security Hardening — IMPLEMENTED (S6.2, S6.3)

Security hardening is active in the production stack:

1. **JWT secret** — generated at startup from `JWT_SECRET_KEY` env var (32-byte hex)
2. **CORS** — locked to `CORS_ORIGINS` env var, no wildcards in production
3. **HTTPS** — enforced by reverse proxy (nginx in docker-compose)
4. **Security headers** — all responses include:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: no-referrer`
   - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
   - `Cross-Origin-Opener-Policy: same-origin`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
   - `Content-Security-Policy` for API routes
5. **Rate limiting** — 5/min register, 10/min login, 100/min general (see `backend/app/rate_limit.py`)
6. **Input validation** — Pydantic models enforce schema on all endpoints
7. **Password policy** — minimum 12 characters (enforced at registration and password change)
8. **Audit logging** — all state-changing operations logged with user, action, IP, timestamp (S3.2)
9. **Encryption at rest** — sensitive columns encrypted with `DATA_ENCRYPTION_KEY` (S3.5)
10. **Row-level security** — tenant isolation enforced at database level (S3.4)

---

## Phase 8: Monitoring & Error Tracking — IMPLEMENTED (S4.4)

Observability is active in the production stack:

### Structured logging
- All logs are JSON-formatted via `structlog` (see `backend/app/observability.py`)
- Every log entry includes `request_id`, `tenant_id`, `user_id`, `action`, `duration_ms`
- Log level controlled by `LOG_LEVEL` env var (default: `INFO`)

### Metrics
- Prometheus metrics exposed at `/metrics` endpoint
- Metrics include: request count, latency histogram, error count by route, active sessions
- Scrape with Prometheus, visualize in Grafana (see `docker-compose.yml` for optional monitoring stack)

### Health checks
- `/api/health/live` — liveness probe (returns 200 if process is running)
- `/api/health/ready` — readiness probe (checks database connectivity, returns 503 if degraded)
- Use these for container orchestration health checks

### Audit trail
- All state-changing operations logged to `audit_logs` table with hash chain (S3.2)
- Verify integrity: `docker compose exec backend python -m scripts.audit_check`
- Export for compliance: `docker compose exec backend python -m scripts.audit_export`

### Error tracking (optional)
- Sentry integration available: set `SENTRY_DSN` env var to enable
- Free tier: 5k errors/month

### Uptime monitoring (recommended)
- Sign up at [UptimeRobot.com](https://uptimerobot.com) (free)
- Monitor: `https://yourdomain.com/api/health/ready`
- Alert via email/Telegram if down

---

## Phase 9: Backup and restore — IMPLEMENTED (S4.5)

[scripts/backup.sh](./scripts/backup.sh) and [scripts/restore.sh](./scripts/restore.sh) work against any Postgres,
managed or not. The retention period for each data class is in [docs/compliance/retention.md](./docs/compliance/retention.md).

### What gets backed up

- **The database**, as a `pg_dump` custom-format archive plus a `.sha256`. Locally, the compose `backup` service writes one every
  `BACKUP_INTERVAL_SECONDS` (default daily) to `BACKUP_HOST_DIR` (default `./backups`). It keeps 35 days of archives and always
  the newest 7. Set `BACKUP_S3_URI` (needs the `aws` CLI in the image) to copy each archive off the host, and use a bucket with
  server-side encryption: the archive holds personal data in clear except for the encrypted columns.
- **Not in the archive:**
  - `DATA_ENCRYPTION_KEY`. Keep it in the secret store, backed up separately. Without it, encrypted columns can't be read and
    audit exports won't match the published public key.
  - The cluster role `finshield_app`. `restore.sh` recreates it.

Run `backup.sh` as the database owner. Under row-level security, a lesser role would silently dump only the rows it can see.

### Restore (tested runbook)

1. **Record the chain heads before you lose them** (or take them from the last backup's run log):
   `docker compose exec backend python -m scripts.audit_check`
2. **Provision an empty database.** Use a new database, or a new cluster after a disaster.
3. **Restore.** Set `DATABASE_URL` to the empty target and run `scripts/restore.sh backups/finshield-<timestamp>.dump`.
   The script:
   - checks the `.sha256`;
   - refuses a non-empty target unless `RESTORE_CLEAN=yes`;
   - recreates `finshield_app`;
   - restores in a single transaction, so a failure leaves nothing half-restored;
   - re-applies the application-role grants.
4. **Start the backend with the original `DATA_ENCRYPTION_KEY`.** The entrypoint's `alembic upgrade head` is a no-op on a
   restored database that is already at head.
5. **Verify the audit trail, twice:**
   `docker compose exec backend python -m scripts.audit_check --export-dir /tmp/audit`
   then `python scripts/verify_audit_export.py /tmp/audit/<tenant>.json --public-key <trusted key>` for each tenant.
   Every tenant must print `OK`, with the same head hash as in step 1.
6. **Re-apply erasures** completed after the backup's timestamp (see the retention doc), then reopen the service.

Restore drill on 2026-10-23, pgvector/pgvector:pg16. The source was the developer database migrated with
`scripts.sqlite_to_postgres`. The target was a fresh cluster with a different superuser and no `finshield_app` role.

```
source   OK   tenant-9bf7…1dac entries=6 head=4a428f24b14c3d091aac14316a79f1f9da055d3416d90a7a37df8720f8878854
backup   finshield-20261023T164726Z.dump (92K), source database dropped
restore  finshield-20261023T164726Z.dump: OK / restore: done, schema revision 0009
again    exit=2 "target has 29 table(s). Restore into an empty database, or set RESTORE_CLEAN=yes."
restored OK   tenant-9bf7…1dac entries=6 head=4a428f24b14c3d091aac14316a79f1f9da055d3416d90a7a37df8720f8878854
verifier chain: OK 6 entries chain from genesis to 4a428f24…8854 / signature: OK signature valid (trusted key)
rls      as owner tenant: 2 transactions; as another tenant: 0 (role finshield_app)
```

The first drill attempt failed: the archive's default privileges named the source owner role. That is why `restore.sh` restores
with `--no-acl` and re-grants. The drill also exposed a pooled-connection RLS bypass, fixed in `app/database.py` with a
regression test.

### Superseded (kept for reference, R7)

The earlier plan assumed Neon:
- Neon auto-backs up (point-in-time restore on paid plan)
- Manual export: `pg_dump $DATABASE_URL > backup.sql` (run weekly)

Managed point-in-time recovery is still worth enabling on any managed Postgres. It complements these archives (which you can
move, verify and restore anywhere) and doesn't replace them.

### Code
- GitHub repo is your source of truth
- Tag releases: `git tag v2.4.0 && git push --tags`

---

## Phase 10: Legal & Compliance (PH)

For operating a fintech SaaS in the Philippines:

| Requirement | Where | Cost |
|-------------|-------|------|
| DTI Business Name | dti.gov.ph | ₱500 |
| Barangay Business Permit | Local barangay | ₱200–500 |
| Mayor's Permit | Municipal/City hall | ₱500–2000 |
| BIR Registration (Form 1901) | bir.gov.ph | Free |
| Official Receipts Book | BIR-authorized printer | ₱500 |
| Privacy Registration (NPC) | privacy.gov.ph | ₱2,400+ |
| Terms of Service | Draft with lawyer | ₱5k–15k |
| Privacy Policy | Draft with lawyer | ₱5k–15k |

> **Note:** If you're only providing screening software (not handling actual money), you likely don't need a BSP license. But if you store/process financial transaction data, register with the National Privacy Commission (NPC) under the Data Privacy Act.

---

## Phase 11: Go-Live Checklist

- [ ] Docker Compose stack deployed on production server
- [ ] Postgres database initialized with migrations (`alembic upgrade head`)
- [ ] Backend health checks passing (`/api/health/ready` returns 200)
- [ ] Frontend accessible at custom domain with HTTPS
- [ ] Stripe live keys configured, test transaction completed
- [ ] SSL/HTTPS active on all domains (TLS 1.2+ enforced)
- [ ] CORS locked to production domains
- [ ] Rate limiting verified (5/min register, 10/min login)
- [ ] Audit trail integrity verified (`python -m scripts.audit_check`)
- [ ] Backup job scheduled (daily via `backup` service in docker-compose)
- [ ] Legal pages live (ToS, Privacy Policy)
- [ ] NPC registration filed (if handling financial transaction data)
- [ ] BIR registered, receipts available
- [ ] Trial system tested end-to-end (signup → 1000 credits → expiry → upgrade)
- [ ] Payment flow tested (Stripe Checkout + Billing)
- [ ] Webhook receiving and processing events
- [ ] Monitoring active (Prometheus metrics, uptime monitor)

---

## Monthly Cost Breakdown

| Service | Free Tier | Paid (if scaling) |
|---------|-----------|-------------------|
| Docker host (VPS) | — | $20/mo (2GB RAM) |
| Postgres (self-hosted) | $0 | Included in VPS |
| Domain | — | ~$1/mo |
| Stripe | $0 | 2.9% + 30¢ per txn |
| UptimeRobot | $0 (50 monitors) | $7/mo |
| Sentry | $0 (5k events) | $26/mo |
| **Total** | **~$21/mo** | **~$54/mo + Stripe fees** |

---

## Quick Start Commands (Local Dev)

```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8091

# Terminal 2 — Frontend
cd platform-app
npm install
npm run dev

# Terminal 3 — Website (optional, static)
cd website
npx serve .
```

---

## Support & Escalation

- Stripe: support@stripe.com (24/7)
- Docker: community forums or Docker Support
- Postgres: community forums or your VPS provider's support
- UptimeRobot: support@uptimerobot.com
- Sentry: support@sentry.io

---

*Last updated: October 2026 — FinShield AI v2.4*
