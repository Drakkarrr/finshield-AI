# FinShield AI — Production Deployment Guide

> Step-by-step guide to take FinShield from local dev to a live, revenue-generating SaaS.
> Written for a solo developer based in the Philippines.

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

## Phase 1: Database (PostgreSQL)

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

7. Test locally with Neon connection, then run migrations:

```bash
cd backend
python -c "from app.database import init_db; init_db()"
```

---

## Phase 2: Backend Deployment (Railway)

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
| `SECRET_KEY` | (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) |
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

## Phase 3: Frontend Deployment (Vercel)

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

## Phase 4: Payment Integration (PayMongo)

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

## Phase 5: Email Notifications (Resend)

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
SECRET_KEY=your-26-hex-char-secret
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

## Phase 8: Monitoring & Error Tracking

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
- Monitor: `https://your-railway-url/api/health`
- Alert via email/Telegram if down

---

## Phase 9: Backup Strategy

### Database (Neon)
- Neon auto-backs up (point-in-time restore on paid plan)
- Manual export: `pg_dump $DATABASE_URL > backup.sql` (run weekly)

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
