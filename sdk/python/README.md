# FinShield Python SDK

A thin client for the FinShield screening API (slice S6.4). It covers screening a transaction, reading
decisions and cases, and verifying webhook signatures. The server's OpenAPI document
(`/api/openapi.json`) is the full reference. The backend test suite checks every path this client
calls against that document.

```bash
pip install ./sdk/python
```

```python
from finshield import FinShield, FinShieldError, verify_webhook

with FinShield("https://api.example.com", api_key="fsk_live_...") as fs:
    d = fs.screen_transaction(amount=25000, currency="USD", transaction_type="wire",
                              sender_name="Acme Ltd", receiver_name="Globex GmbH",
                              destination_country="DE", idempotency_key="payment-1234")
    print(d["status"], d["risk_score"])   # e.g. "flagged" 0.62
    for reason in d["reasons"]:           # why: rule hits, list matches, model contribution
        print(reason["source"], reason["feature"], reason.get("detail"))

    page, total = fs.list_transactions(limit=50, offset=0)
```

- **Idempotency.** Pass your own `idempotency_key`. A retried call with the same key returns the
  original decision instead of screening the transaction again.
- **Errors.** A non-2xx response raises `FinShieldError`. It carries `.status`, the API's `.detail`
  and `.request_id`, so you can quote the request when you contact support.
- **Webhooks.** Pass the raw request body:
  `verify_webhook(body, request.headers["X-FinShield-Signature"], secret)`. It rejects a delivery
  if the signature doesn't match or the delivery is more than 5 minutes old.
