"""Celery application and beat schedule (S4.1, S4.3; ruling D2).

HARD RULE: no screening-decision logic runs here. Decisions stay synchronous and auditable in the
API; the worker only delivers, sweeps, refreshes and recomputes.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

app = Celery("finshield", broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
             include=["app.worker.tasks"])

app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,  # a crash mid-task re-delivers it; every task is idempotent
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    # Tests (and single-process debugging) run tasks inline.
    task_always_eager=os.getenv("APP_ENV") == "test" or os.getenv("CELERY_TASK_ALWAYS_EAGER") == "true",
    beat_schedule={
        "webhook-outbox": {"task": "finshield.webhooks.outbox_sweep", "schedule": 60.0},
        "audit-seal": {"task": "finshield.audit.seal", "schedule": 60.0},
        "sla-sweep": {"task": "finshield.cases.sla_sweep", "schedule": 300.0},
        "audit-verify": {"task": "finshield.audit.verify", "schedule": crontab(minute=7)},
        "filing-deadlines": {"task": "finshield.filings.deadline_reminders", "schedule": crontab(hour=6, minute=0)},
        "privacy-deadlines": {"task": "finshield.privacy.deadline_sweep", "schedule": crontab(hour=6, minute=15)},
        "list-refresh": {"task": "finshield.lists.refresh", "schedule": crontab(hour=4, minute=0)},
        "baseline-recompute": {"task": "finshield.behavioral.recompute_baselines", "schedule": crontab(hour=3, minute=0)},
        "rag-staleness": {"task": "finshield.rag.staleness_check", "schedule": crontab(hour=5, minute=0)},
    },
)
