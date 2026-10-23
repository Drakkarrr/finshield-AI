"""Background tasks. Naming: finshield.<domain>.<action>. Arguments are ids, never personal data.

Every task is idempotent and records its runs in job_runs via LedgerTask; a task that exhausts its
retries is left there as status=dead_letter for an operator (python -m scripts.jobs).
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator

from celery import Task
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import metrics
from app.database import SessionLocal, SideSession
from app.db_models import (
    Filing,
    JobRun,
    ListImport,
    Notification,
    PrivacyRequest,
    Tenant,
    Transaction,
    User,
    WebhookEvent,
)
from app.worker.celery_app import app

logger = logging.getLogger("finshield.worker")


class LedgerTask(Task):
    """Retries with exponential backoff + jitter; every attempt is recorded in job_runs."""
    autoretry_for = (Exception,)
    retry_backoff = 5
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3

    def _record(self, task_id: str, **fields: Any) -> None:
        db = SideSession()
        try:
            row = db.get(JobRun, task_id)
            if row is None:
                row = JobRun(id=task_id, task=self.name, started_at=datetime.utcnow())
                db.add(row)
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
        except Exception:  # bookkeeping must never fail the task it describes
            logger.exception("could not record job run %s", task_id)
        finally:
            db.close()

    def before_start(self, task_id, args, kwargs):
        self._record(task_id, args={"args": list(args), "kwargs": kwargs}, status="started",
                     attempts=self.request.retries + 1)

    def on_success(self, retval, task_id, args, kwargs):
        self._record(task_id, status="succeeded", result=retval if isinstance(retval, (dict, list)) else None,
                     finished_at=datetime.utcnow())
        metrics.JOB_RUNS.labels(task=self.name, status="succeeded").inc()

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        self._record(task_id, status="retrying", last_error=f"{type(exc).__name__}: {exc}"[:1000])
        metrics.JOB_RUNS.labels(task=self.name, status="retrying").inc()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        self._record(task_id, status="dead_letter", last_error=f"{type(exc).__name__}: {exc}"[:1000],
                     finished_at=datetime.utcnow())
        metrics.JOB_RUNS.labels(task=self.name, status="dead_letter").inc()
        logger.error("task %s dead-lettered after %s attempt(s): %s", self.name, self.request.retries + 1, exc)


@contextmanager
def system_session() -> Iterator[Session]:
    """Cross-tenant session for system jobs (explicit RLS bypass)."""
    db = SessionLocal()
    db.info["rls_bypass"] = True
    try:
        yield db
    finally:
        db.close()


def _tenants(db: Session) -> list[str]:
    return [t for (t,) in db.query(Tenant.id).order_by(Tenant.id).all()]


@contextmanager
def tenant_session(tenant_id: str) -> Iterator[Session]:
    """A session bound to one tenant (RLS applies), for per-tenant work."""
    db = SessionLocal()
    db.info["tenant_id"] = tenant_id
    try:
        yield db
    finally:
        db.close()


# --- webhooks -----------------------------------------------------------------------------------
@app.task(base=LedgerTask, name="finshield.webhooks.deliver", max_retries=0)
def deliver_webhook(event_id: str) -> dict:
    from app.domain import webhooks

    outcome = webhooks.deliver(event_id)
    metrics.WEBHOOK_DELIVERIES.labels(result=outcome.get("result", outcome.get("status", "unknown"))).inc()
    if outcome.get("result") == "retry":
        deliver_webhook.apply_async(args=[event_id], countdown=outcome["retry_in_s"])
    return outcome


@app.task(base=LedgerTask, name="finshield.webhooks.outbox_sweep")
def webhook_outbox_sweep() -> dict:
    """Enqueue pending events older than a minute (broker was down at commit) and retries now due."""
    now = datetime.utcnow()
    with system_session() as db:
        stale = [i for (i,) in db.query(WebhookEvent.id).filter(
            WebhookEvent.status == "pending", WebhookEvent.created_at <= now - timedelta(minutes=1)).all()]
        due = [i for (i,) in db.query(WebhookEvent.id).filter(
            WebhookEvent.status == "failed", WebhookEvent.next_retry_at <= now).all()]
    for event_id in stale + due:
        deliver_webhook.delay(event_id)
    return {"pending": len(stale), "retries_due": len(due)}


# --- cases / filings / privacy ------------------------------------------------------------------
@app.task(base=LedgerTask, name="finshield.cases.sla_sweep")
def sla_sweep() -> dict:
    from app.domain.cases import sla_sweep as sweep

    with system_session() as db:
        tenants = _tenants(db)
    totals = {"escalated": 0, "approaching_notified": 0}
    for tenant_id in tenants:
        with tenant_session(tenant_id) as db:
            for k, v in sweep(db, tenant_id).items():
                totals[k] += v
    return totals


def _notify_once(db: Session, tenant_id: str, user_ids: list[str], kind: str, title: str, message: str,
                 link: str, since: datetime) -> int:
    sent = 0
    for uid in user_ids:
        exists = db.query(Notification).filter(Notification.user_id == uid, Notification.type == kind,
                                               Notification.link == link, Notification.created_at >= since).first()
        if not exists:
            db.add(Notification(tenant_id=tenant_id, user_id=uid, type=kind, title=title, message=message, link=link))
            sent += 1
    return sent


def _supervisors(db: Session, tenant_id: str) -> list[str]:
    return [u for (u,) in db.query(User.id).filter(User.tenant_id == tenant_id, User.is_active == True,  # noqa: E712
                                                   User.role.in_(("supervisor", "admin"))).all()]


@app.task(base=LedgerTask, name="finshield.filings.deadline_reminders")
def filing_deadline_reminders() -> dict:
    """One reminder per filing per day while it is unsubmitted and due within filings.reminder_days."""
    from app import config_service

    now = datetime.utcnow()
    sent = 0
    with system_session() as db:
        tenants = _tenants(db)
    for tenant_id in tenants:
        with tenant_session(tenant_id) as db:
            window = now + timedelta(days=float(config_service.get_setting(db, "filings.reminder_days")))
            for f in db.query(Filing).filter(Filing.tenant_id == tenant_id, Filing.status.in_(("draft", "under_review")),
                                             Filing.deadline.isnot(None), Filing.deadline <= window).all():
                days = (f.deadline - now).days if f.deadline else 0
                sent += _notify_once(db, tenant_id, list({f.user_id, *_supervisors(db, tenant_id)}), "filing_deadline",
                                     "Filing deadline approaching" if days >= 0 else "Filing overdue",
                                     f"{f.filing_type} filing {f.id} is due {f.deadline.date().isoformat() if f.deadline else '?'}"
                                     f" ({days} day(s)).", f"/filings?filing={f.id}", now - timedelta(days=1))
            db.commit()
    return {"reminders": sent}


@app.task(base=LedgerTask, name="finshield.privacy.deadline_sweep")
def privacy_deadline_sweep() -> dict:
    """Daily notice to supervisors about data-subject requests due within 3 days or overdue."""
    now = datetime.utcnow()
    sent = 0
    with system_session() as db:
        tenants = _tenants(db)
    for tenant_id in tenants:
        with tenant_session(tenant_id) as db:
            for r in db.query(PrivacyRequest).filter(PrivacyRequest.tenant_id == tenant_id,
                                                     PrivacyRequest.status == "received",
                                                     PrivacyRequest.due_at <= now + timedelta(days=3)).all():
                sent += _notify_once(db, tenant_id, _supervisors(db, tenant_id), "privacy_deadline",
                                     "Privacy request overdue" if r.due_at < now else "Privacy request due soon",
                                     f"{r.request_type} request {r.id} is due {r.due_at.date().isoformat()}.",
                                     f"/settings?privacy={r.id}", now - timedelta(days=1))
            db.commit()
    return {"notices": sent}


# --- behavioral / lists / audit / RAG ---------------------------------------------------------------
@app.task(base=LedgerTask, name="finshield.behavioral.recompute_baselines")
def recompute_baselines() -> dict:
    from app import screening_service

    since = datetime.utcnow() - timedelta(days=screening_service.HISTORY_DAYS)
    done = 0
    with system_session() as db:
        accounts = db.query(Transaction.tenant_id, Transaction.account_id, func.max(Transaction.user_id)).filter(
            Transaction.account_id.isnot(None), Transaction.created_at >= since).group_by(
            Transaction.tenant_id, Transaction.account_id).all()
    for tenant_id, account_id, user_id in accounts:
        with tenant_session(tenant_id) as db:
            if screening_service.refresh_baseline(db, tenant_id, user_id, account_id) is not None:
                done += 1
            db.commit()
    return {"baselines": done}


@app.task(base=LedgerTask, name="finshield.lists.refresh")
def refresh_lists() -> dict:
    """Re-import the official OFAC SDN export when its content changed (LISTS_AUTO_DOWNLOAD=true)."""
    if os.getenv("LISTS_AUTO_DOWNLOAD", "false").lower() != "true":
        return {"skipped": "LISTS_AUTO_DOWNLOAD is off"}
    from app.domain.lists.importers import OFAC_SOURCE, parse_ofac_sdn
    from app.domain.lists.provider import store_import
    from scripts.import_lists import _download

    entries, version = parse_ofac_sdn(_download("SDN.CSV"), _download("ALT.CSV"), _download("ADD.CSV"))
    with system_session() as db:
        latest = db.query(ListImport).filter(ListImport.source == OFAC_SOURCE).order_by(ListImport.id.desc()).first()
        if latest is not None and latest.list_version == version:
            return {"source": OFAC_SOURCE, "version": version, "changed": False}
        if not entries:
            raise RuntimeError("refusing to import an empty sanctions list")
        store_import(db, entries, OFAC_SOURCE, "sanctions", version)
    return {"source": OFAC_SOURCE, "version": version, "changed": True, "entries": len(entries)}


@app.task(base=LedgerTask, name="finshield.audit.seal")
def seal_audit() -> dict:
    from app.domain import audit

    with system_session() as db:
        tenants = _tenants(db)
    sealed = 0
    for tenant_id in tenants:
        with system_session() as db:
            sealed += audit.seal(db, tenant_id)
    return {"sealed": sealed}


@app.task(base=LedgerTask, name="finshield.audit.verify")
def verify_audit() -> dict:
    """Seal and verify every tenant's chain; a break is logged as an error, counted, and notified."""
    from app.domain import audit

    with system_session() as db:
        tenants = _tenants(db)
    broken = []
    for tenant_id in tenants:
        with system_session() as db:
            result = audit.verify(db, tenant_id)
            if not result["ok"]:
                broken.append({"tenant_id": tenant_id, "first_break_seq": result["first_break_seq"]})
                metrics.AUDIT_CHAIN_BREAKS.inc()
                logger.error("AUDIT CHAIN BROKEN tenant=%s at seq=%s", tenant_id, result["first_break_seq"])
                _notify_once(db, tenant_id, _supervisors(db, tenant_id), "audit_chain_broken", "Audit chain broken",
                             f"Audit verification failed at entry {result['first_break_seq']}.", "/settings?audit=verify",
                             datetime.utcnow() - timedelta(hours=1))
                db.commit()
    return {"tenants": len(tenants), "broken": broken}


@app.task(base=LedgerTask, name="finshield.rag.staleness_check")
def rag_staleness_check() -> dict:
    url = os.getenv("RAG_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        return {"rag": "disabled"}
    from app.domain.rag.embedders import load_embedder
    from app.domain.rag.service import RAGRetrievalService

    service = RAGRetrievalService(url, load_embedder())
    stored = service.model_status()
    stale = {t: m for t, m in stored.items() if m and m != [service.embedder.name]}
    empty = [t for t, n in service.counts().items() if n == 0]
    if stale or empty:
        logger.warning("RAG corpus stale=%s empty=%s (re-embed: python -m scripts.bootstrap --reembed)", stale, empty)
    metrics.RAG_STALE.set(1 if (stale or empty) else 0)
    return {"embedder": service.embedder.name, "stale": stale, "empty": empty}


# --- operations -------------------------------------------------------------------------------------
@app.task(base=LedgerTask, name="finshield.ops.selftest")
def selftest(fail: bool = False) -> dict:
    """Exercises the worker path end to end; fail=True walks the retry -> dead-letter path."""
    if fail:
        raise RuntimeError("selftest failure requested")
    return {"ok": True, "at": datetime.utcnow().isoformat()}
