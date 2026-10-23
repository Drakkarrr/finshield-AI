---
kind: external_dependency
name: Resend email delivery
slug: resend
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
source_files:
    - DEPLOYMENT.md
---

### Identity
Resend (resend.com) — transactional email provider used for trial expiry reminders and notifications.

### Planned integration
- API key injected via `RESEND_API_KEY` env var; `resend.api_key` initialized in `backend/app/email.py`.
- Sends HTML emails from `notifications@yourdomain.com`.

### Status
- Only the snippet in `DEPLOYMENT.md` exists; no `backend/app/email.py` or `resend` dependency in `requirements.txt`.