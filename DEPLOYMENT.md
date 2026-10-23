# FinShield AI — Production Deployment Guide

> Step-by-step guide to take FinShield from local dev to a live, revenue-generating SaaS.
> Written for a solo developer based in the Philippines.

> **Status: PROPOSED.** Nothing in this guide has been deployed or automated, and no Railway/Vercel/Neon/PayMongo/Resend/Sentry/UptimeRobot integration exists in the code (there is no `backend/app/payment.py`). Sections marked **PROPOSED** describe a plan, not a working setup. Rulings in [MASTER-PROMPT.md §2](./docs/architecture/evolution/MASTER-PROMPT.md) govern the eventual design: managed PaaS with the platform secret store (D9 — Railway/Vercel fit), Postgres primary (D6), **Stripe** for payments (D8 — replaces PayMongo below). The product is not production-ready; see [evolution-summary.md](./docs/architecture/evolution/evolution-summary.md) for the blockers. For running locally today, follow the [README quick start](./README.md#quick-start).

---

## Prerequisites Checklist

Before starting, make sure you have:

- [ ] A domain name (buy from [Porkbun](https://porkbun.com) or [Namecheap](https://namecheap.com), ~$10/yr)
- [ ] GitHub account with repo access
- [ ] A business registration (DTI for sole prop, or SEC for corporation)
- [ ] BIR registration (for issuing official receipts)
- [ ] PayMongo account (sign up at [paymongo.com](https://paymongo.com))
- [ ] A Philippine bank account (for PayMongo payouts)
- [ ] Node.js 18+ and Python 3.11+ on your local machine

---

## Phase 1: Database (PostgreSQL) — PROPOSED

SQLite doesn't work in production. Use **Neon** (free tier, serverless Postgres).

### Steps

1. Go to [neon.tech](https://neon.tech) → Sign up with GitHub
2. Create a project: name = `finshield-prod`, region = `Singapore (ap-southeast-1)`
3. Copy the connection string (looks like `postgresql://user:pass@ep-xxx.neon.tech/dbname`)
4. Update your backend `.env`:

```bash
# backend/.env
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/finshield?sslmode=require
```

5. Install the Postgres driver:

```bash
cd backend
pip install psycopg2-binary
```

6. Update `app/database.py` — change the DATABASE_URL logic:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finshield.db")
```

7. Test locally with the Neon connection, then create the tables:

```bash
cd backend
python -c "from app.database import init_db; init_db()"
```

`init_db()` runs SQLAlchemy `create_all`: it creates missing tables but never alters existing ones. Alembic migrations are not yet adopted (roadmap slice S1.2); until then, any schema change requires manual DDL on an existing database.

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

## Phase 4: Payment Integration (PayMongo) — PROPOSED, superseded by ruling D8 (Stripe)

> **Superseded.** Ruling D8 selects Stripe Checkout + Stripe Billing, storing only Stripe customer/subscription/payment-method ids (roadmap slice S6.1). The PayMongo plan below is kept for reference only. Note that today the backend has plaintext card columns and a simulated checkout — do not take real payments with it.

PayMongo is the best option for PH-based SaaS. Supports cards, GCash, Maya.

### Setup

1. Sign up at [paymongo.com](https://paymongo.com) → Complete KYC (submit DTI/SEC + bank info)
2. Get your **Secret Key** from Dashboard → API Keys
3. Install the SDK:

```bash
cd backend
pip install paymongo
```

### Implementation

Create `backend/app/payment.py`:

```python
"""PayMongo integration for FinShield credit purchases."""
import os
import httpx

PAYMONGO_SECRET = os.getenv("PAYMONGO_SECRET_KEY")
PAYMONGO_API = "https://api.paymongo.com/v1"

async def create_checkout_session(credits: int, price_usd: float, success_url: str, cancel_url: str) -> dict:
    """Create a PayMongo Checkout session for credit purchase."""
    amount_in_centavos = int(price_usd * 50 * 100)  # USD to PHP approx, then to centavos

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYMONGO_API}/checkout_sessions",
            auth=(PAYMONGO_SECRET, ""),
            json={
                "data": {
                    "attributes": {
                        "description": f"FinShield {credits:,} Credits",
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                        "line_items": [{
                            "name": f"FinShield {credits:,} Credits",
                            "quantity": 1,
                            "amount": amount_in_centavos,
                            "currency": "PHP",
                        }],
                        "metadata": {"credits": credits},
                    }
                }
            }
        )
        return resp.json()

async def verify_payment(payment_intent_id: str) -> bool:
    """Verify a payment was successfully completed."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PAYMONGO_API}/payment_intents/{payment_intent_id}",
            auth=(PAYMONGO_SECRET, ""),
        )
        data = resp.json()
        return data["data"]["attributes"]["status"] == "succeeded"
```

### Wire it into the checkout endpoint

Replace the simulated checkout in `main.py`:

```python
from app.payment import create_checkout_session, verify_payment

@app.post("/api/v1/credits/checkout", tags=["Billing"])
async def checkout_credits(req: CheckoutRequest, current_user, db):
    """Create PayMongo checkout session."""
    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit pack")
    price = CREDIT_PACKS[req.credits]

    session = await create_checkout_session(
        credits=req.credits,
        price_usd=price,
        success_url=f"https://yourdomain.com/settings?tab=billing&payment=success&credits={req.credits}",
        cancel_url="https://yourdomain.com/settings?tab=billing&payment=cancelled",
    )
    return {"checkout_url": session["data"]["attributes"]["url"], "session_id": session["data"]["id"]}
```

### Handle webhook (payment confirmation)

```python
@app.post("/api/webhooks/paymongo", tags=["Webhooks"])
async def paymongo_webhook(request: Request, db: Session = Depends(get_db)):
    """PayMongo webhook — called when payment status changes."""
    body = await request.json()
    event_type = body.get("data", {}).get("attributes", {}).get("type")

    if event_type == "payment_intent.succeeded":
        credits = body["data"]["attributes"]["metadata"]["credits"]
        user_id = body["data"]["attributes"]["metadata"]["user_id"]
        # Add credits to user
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_credits += credits
            db.commit()
            # Create notification
            notif = Notification(
                user_id=user.id, type="credit_alert",
                title="Credits purchased",
                message=f"{credits:,} credits added successfully.",
                link="/settings?tab=billing",
            )
            db.add(notif)
            db.commit()

    return {"status": "received"}
```

### Set up webhook in PayMongo Dashboard

- URL: `https://your-railway-url.up.railway.app/api/webhooks/paymongo`
- Events: `payment_intent.succeeded`, `payment_intent.payment_failed`

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
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/finshield?sslmode=require
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
APP_ENV=production
DEBUG=false

# PayMongo
PAYMONGO_SECRET_KEY=sk_live_xxxxx

# Resend
RESEND_API_KEY=re_xxxxx

# Optional: Sentry
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

---

## Phase 7: Security Hardening

### Must-do before going live:

1. **Rotate JWT secret** — use `python -c "import secrets; print(secrets.token_hex(32))"`
2. **Set CORS to production domain only** — no wildcards
3. **Enable HTTPS** — automatic on Railway + Vercel
4. **Rate limiting** — already configured, verify it's active
5. **Remove test accounts** from production DB
6. **Set `DEBUG=false`** — never expose stack traces
7. **Add security headers** in `main.py`:

```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

8. **Input validation** — already handled by Pydantic, but add rate limiting to auth endpoints (done: 5/min register, 10/min login)

---

## Phase 8: Monitoring & Error Tracking — PROPOSED

### Sentry (free tier: 5k errors/month)

```bash
cd backend
pip install sentry-sdk
```

In `main.py` (top of file):

```python
import sentry_sdk
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,
)
```

### Uptime Monitoring

- Sign up at [UptimeRobot.com](https://uptimerobot.com) (free)
- Monitor: `https://your-railway-url/api/health/ready` (probes the database and returns 503 when degraded — slice S0.4; before S0.4, `/api/health` returned a hardcoded "healthy" and must not be used for monitoring)
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

- [ ] Database migrated to Neon PostgreSQL
- [ ] Backend deployed to Railway, health check passing
- [ ] Frontend deployed to Vercel with custom domain
- [ ] PayMongo live keys configured, test transaction completed
- [ ] Email sending works (Resend domain verified)
- [ ] SSL/HTTPS active on all domains
- [ ] CORS locked to production domains
- [ ] Rate limiting verified
- [ ] Sentry connected and receiving events
- [ ] Uptime monitor active
- [ ] Backup job scheduled
- [ ] Legal pages live (ToS, Privacy Policy)
- [ ] NPC registration filed
- [ ] BIR registered, receipts available
- [ ] Trial system tested end-to-end (signup → 1000 credits → expiry → upgrade)
- [ ] Payment flow tested (GCash + card)
- [ ] Webhook receiving and processing events

---

## Monthly Cost Breakdown

| Service | Free Tier | Paid (if scaling) |
|---------|-----------|-------------------|
| Neon (Postgres) | $0 (0.5GB) | $19/mo |
| Railway (Backend) | $0 (500hrs) | $20/mo |
| Vercel (Frontend) | $0 (Hobby) | $20/mo |
| PayMongo | $0 (per-txn only) | ~2.5% per txn |
| Resend (Email) | $0 (100/day) | $20/mo |
| Domain | — | ~$1/mo |
| Sentry | $0 (5k events) | $26/mo |
| **Total** | **~$1/mo** | **~$106/mo** |

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

- PayMongo: support@paymongo.com (PH business hours)
- Neon: community Slack or support@neon.tech
- Railway: Discord community or support@railway.app
- Vercel: Built-in chat support

---

*Last updated: October 2026 — FinShield AI v2.4*
