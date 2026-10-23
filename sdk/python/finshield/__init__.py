"""FinShield Python SDK (S6.4): screen transactions, read decisions, verify webhooks.

    from finshield import FinShield

    fs = FinShield("https://api.example.com", api_key="fsk_live_...")
    decision = fs.screen_transaction(amount=25000, currency="USD", transaction_type="wire",
                                     sender_name="Acme Ltd", receiver_name="Globex GmbH",
                                     idempotency_key="order-1234")
    print(decision["status"], decision["risk_score"], decision["reasons"])

The API is the source of truth (ruling D10): this client is a thin layer over the documented
endpoints, and tests check every path it calls against the server's OpenAPI document.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import Any, Optional

import httpx

__all__ = ["FinShield", "FinShieldError", "verify_webhook"]
__version__ = "0.1.0"

SIGNATURE_HEADER = "X-FinShield-Signature"


class FinShieldError(Exception):
    """A non-2xx response. `status` is the HTTP status, `detail` the API's error message."""

    def __init__(self, status: int, detail: Any, request_id: Optional[str] = None):
        super().__init__(f"HTTP {status}: {detail}")
        self.status, self.detail, self.request_id = status, detail, request_id


class FinShield:
    """Synchronous client. Pass `http_client` to reuse a configured httpx.Client (proxies, tests)."""

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 30.0,
                 http_client: Optional[httpx.Client] = None):
        self._http = http_client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}", "User-Agent": f"finshield-python/{__version__}"}

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "FinShield":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        r = self._http.request(method, path, headers=self._headers, **kwargs)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise FinShieldError(r.status_code, detail, r.headers.get("X-Request-ID"))
        return r

    # --- screening ---------------------------------------------------------------------------
    def screen_transaction(self, *, amount: float, transaction_type: str, sender_name: str, receiver_name: str,
                           currency: str = "USD", idempotency_key: Optional[str] = None, **fields: Any) -> dict:
        """Screen one transaction and return the decision (status, risk_score, reasons...).

        Send a stable `idempotency_key` (e.g. your payment id) so a retried call returns the
        original decision instead of screening twice. Other optional fields: sender_id, account_id,
        receiver_id, destination_country, description, metadata."""
        body = {"amount": amount, "currency": currency, "transaction_type": transaction_type,
                "sender_name": sender_name, "receiver_name": receiver_name,
                "idempotency_key": idempotency_key or str(uuid.uuid4()), **fields}
        return self._request("POST", "/api/v1/transactions", json=body).json()["data"]

    def get_transaction(self, transaction_id: str) -> dict:
        return self._request("GET", f"/api/v1/transactions/{transaction_id}").json()

    def list_transactions(self, *, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        """One page of transactions, newest first, and the total count."""
        r = self._request("GET", "/api/v1/transactions", params={"limit": limit, "offset": offset})
        return r.json(), int(r.headers.get("X-Total-Count", "0"))

    # --- cases -------------------------------------------------------------------------------
    def list_cases(self) -> list[dict]:
        return self._request("GET", "/api/v1/cases").json()

    def get_case(self, case_id: str) -> dict:
        return self._request("GET", f"/api/v1/cases/{case_id}").json()


def verify_webhook(payload: bytes, signature_header: str, secret: str, *, tolerance_s: int = 300,
                   now: Optional[int] = None) -> bool:
    """Check the X-FinShield-Signature header of a webhook delivery.

    The header is `t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>." + raw body)>`. Pass the raw
    request body exactly as received. Deliveries older than `tolerance_s` are rejected (replays)."""
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    try:
        ts = int(parts["t"])
        received = parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs((now if now is not None else int(time.time())) - ts) > tolerance_s:
        return False
    expected = hmac.new(secret.encode("utf-8"), f"{ts}.".encode("ascii") + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
