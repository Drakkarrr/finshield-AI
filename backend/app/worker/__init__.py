"""FinShield AI — Celery worker configuration (S4.1)."""
import os

from celery import Celery

# Redis broker URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "finshield",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"],
)

# Configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Dead letter queue
    task_routes={
        "app.worker.tasks.*": {"queue": "default"},
    },
    
    # Result backend
    result_expires=86400,  # 24 hours
    
    # Worker
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Beat schedule for periodic tasks (S4.3)
celery_app.conf.beat_schedule = {
    "sla-sweep": {
        "task": "app.worker.tasks.sla_sweep",
        "schedule": 300.0,  # Every 5 minutes
    },
    "baseline-recompute": {
        "task": "app.worker.tasks.recompute_behavioral_baselines",
        "schedule": 86400.0,  # Daily
    },
    "dsar-sweep": {
        "task": "app.worker.tasks.process_pending_dsar_requests",
        "schedule": 3600.0,  # Hourly
    },
    "chain-verification": {
        "task": "app.worker.tasks.verify_audit_chain_integrity",
        "schedule": 21600.0,  # Every 6 hours
    },
    "filing-reminders": {
        "task": "app.worker.tasks.send_filing_reminders",
        "schedule": 43200.0,  # Every 12 hours
    },
    "list-refresh": {
        "task": "app.worker.tasks.refresh_sanctions_lists",
        "schedule": 604800.0,  # Weekly (7 days)
    },
}
