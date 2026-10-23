"""Webhooks (S4.2): transactional outbox, HMAC-signed delivery, backoff, dead-letter queue.

emit() writes one webhook_events row per matching subscription in the CALLER'S transaction, so an
event exists iff the lifecycle change committed. Rows are handed to the worker only after commit;
if the broker is down, the outbox sweep picks them up later. Payloads carry ids and decisions, never
personal data: integrators fetch details through the API with their own credentials.

Signature: header X-FinShield-Signature: t=<unix ts>,v1=<hex HMAC-SHA256(secret, f"{t}.{body}")>.
Receivers recompute it over the raw body and reject timestamps older than their tolerance.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from app import config_service, crypto
from app.database import SessionLocal
from app.db_models import WebhookEvent, WebhookSubscription

logger = logging.getLogger("finshield.webhooks")

EVENT_TYPES = ("transaction.flagged", "transaction.blocked", "case.created", "case.updated", "case.resolved",
               "filing.submitted", "sla.breached")
PENDING_KEY = "pending_webhook_events"
MAX_BACKOFF_S = 6 * 3600

# Tests inject an httpx transport here; production uses the real network.
http_transport: Optional[httpx.BaseTransport] = None


class TargetNotAllowed(ValueError):
    pass


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def signature(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("ascii") + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


def verify_signature(secret: str, header: str, body: bytes, tolerance_s: int = 300, now: Optional[int] = None) -> bool:
    """Reference receiver-side check (documented for integrators)."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        ts = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs((now or int(time.time())) - ts) > tolerance_s:
        return False
    return hmac.compare_digest(signature(secret, ts, body), header)


def check_target(db: Session, url: str) -> None:
    """SSRF guard: https only and no private/loopback/link-local targets unless explicitly allowed
    (webhooks.allow_http / webhooks.allow_private_targets). Checked at subscribe AND at delivery,
    because DNS can change in between."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise TargetNotAllowed("URL must be http(s) with a host")
    if parsed.scheme == "http" and not config_service.get_setting(db, "webhooks.allow_http"):
        raise TargetNotAllowed("https is required (webhooks.allow_http is off)")
    if config_service.get_setting(db, "webhooks.allow_private_targets"):
        return
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise TargetNotAllowed(f"cannot resolve {parsed.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise TargetNotAllowed(f"{parsed.hostname} resolves to a non-public address")


def emit(db: Session, tenant_id: str, event_type: str, payload: dict, user_id: Optional[str] = None) -> int:
    """Queue `event_type` for every active subscription of the tenant that wants it."""
    assert event_type in EVENT_TYPES, event_type
    subs = db.query(WebhookSubscription).filter(WebhookSubscription.tenant_id == tenant_id,
                                                WebhookSubscription.active == True).all()  # noqa: E712
    body = {"type": event_type, "created_at": datetime.utcnow().isoformat(), "data": payload}
    rows = [WebhookEvent(tenant_id=tenant_id, user_id=user_id, subscription_id=s.id, event_type=event_type,
                         payload=body, status="pending", attempts=0, attempt_log=[])
            for s in subs if "*" in (s.events or []) or event_type in (s.events or [])]
    db.add_all(rows)
    db.flush()
    db.info.setdefault(PENDING_KEY, []).extend(r.id for r in rows)
    return len(rows)


@sa_event.listens_for(SessionLocal, "after_commit")
def _enqueue_after_commit(session: Session) -> None:
    ids = session.info.pop(PENDING_KEY, [])
    if not ids:
        return
    from app.worker import tasks  # late import: the worker imports the app

    for event_id in ids:
        try:
            tasks.deliver_webhook.delay(event_id)
        except Exception:  # broker down: the outbox sweep delivers it later
            logger.warning("could not enqueue webhook %s; the outbox sweep will retry", event_id, exc_info=True)


@sa_event.listens_for(SessionLocal, "after_rollback")
def _drop_on_rollback(session: Session) -> None:
    session.info.pop(PENDING_KEY, None)


def backoff_seconds(attempt: int, base: float) -> float:
    """Exponential backoff with full jitter on top: base * 2^(attempt-1) + [0, base)."""
    return min(MAX_BACKOFF_S, base * 2 ** (attempt - 1) + secrets.randbelow(max(int(base * 1000), 1)) / 1000)


def deliver(event_id: str) -> dict[str, Any]:
    """One delivery attempt. Returns the outcome; the task schedules the retry it names."""
    db = SessionLocal()
    db.info["rls_bypass"] = True  # system job: the event's tenant is bound below for settings
    try:
        ev = db.get(WebhookEvent, event_id)
        if ev is None or ev.status in ("delivered", "dead_letter"):
            return {"status": ev.status if ev else "missing"}
        db.info["tenant_id"] = ev.tenant_id
        sub = db.get(WebhookSubscription, ev.subscription_id) if ev.subscription_id else None
        now = datetime.utcnow()
        attempt = (ev.attempts or 0) + 1
        record: dict[str, Any] = {"attempt": attempt, "at": now.isoformat()}
        try:
            if sub is None or not sub.active:
                raise TargetNotAllowed("subscription missing or inactive")
            check_target(db, sub.url)
            body = json.dumps({"id": ev.id, **ev.payload}, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ts = int(time.time())
            headers = {"Content-Type": "application/json", "User-Agent": "FinShield-Webhooks/1",
                       "X-FinShield-Event": ev.event_type, "X-FinShield-Delivery": ev.id,
                       "X-FinShield-Signature": signature(crypto.decrypt_json(sub.secret_enc), ts, body)}
            with httpx.Client(transport=http_transport, timeout=float(config_service.get_setting(
                    db, "webhooks.timeout_seconds")), follow_redirects=False) as client:
                resp = client.post(sub.url, content=body, headers=headers)
            record["status_code"] = ev.response_code = resp.status_code
            if not 200 <= resp.status_code < 300:
                raise RuntimeError(f"subscriber returned HTTP {resp.status_code}")
            ev.status, ev.delivered_at, ev.last_error, ev.next_retry_at = "delivered", now, None, None
            record["result"] = "delivered"
        except Exception as e:
            ev.last_error = record["error"] = f"{type(e).__name__}: {e}"[:500]
            permanent = isinstance(e, TargetNotAllowed)
            if permanent or attempt >= int(config_service.get_setting(db, "webhooks.max_attempts")):
                ev.status, ev.next_retry_at = "dead_letter", None
                record["result"] = "dead_letter"
            else:
                delay = backoff_seconds(attempt, float(config_service.get_setting(db, "webhooks.backoff_base_seconds")))
                ev.status, ev.next_retry_at = "failed", now + timedelta(seconds=delay)
                record["result"], record["retry_in_s"] = "retry", round(delay, 3)
        ev.attempts, ev.last_attempt_at = attempt, now
        ev.attempt_log = [*(ev.attempt_log or []), record]
        db.commit()
        return record
    finally:
        db.close()
