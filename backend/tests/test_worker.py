"""Tests for Celery worker tasks (S4.1)."""
import pytest


def test_worker_module_imports():
    """Test that worker module can be imported."""
    from app.worker import celery_app
    from app.worker.tasks import health_check, sla_sweep, process_pending_dsar_requests
    
    assert celery_app is not None
    assert health_check is not None
    assert sla_sweep is not None


def test_health_check_task():
    """Test health check task returns healthy status."""
    from app.worker.tasks import health_check
    
    result = health_check()
    assert result["status"] == "healthy"
    assert result["worker"] == "finshield-worker"
    assert "timestamp" in result


def test_celery_app_configuration():
    """Test Celery app is configured correctly."""
    from app.worker import celery_app
    
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.task_acks_late is True
    assert "sla-sweep" in celery_app.conf.beat_schedule
    assert "baseline-recompute" in celery_app.conf.beat_schedule
    assert "dsar-sweep" in celery_app.conf.beat_schedule
    assert "chain-verification" in celery_app.conf.beat_schedule
    assert "filing-reminders" in celery_app.conf.beat_schedule
    assert "list-refresh" in celery_app.conf.beat_schedule


def test_all_scheduled_tasks_exist():
    """Test that all scheduled tasks are defined."""
    from app.worker.tasks import (
        sla_sweep,
        recompute_behavioral_baselines,
        process_pending_dsar_requests,
        verify_audit_chain_integrity,
        send_filing_reminders,
        refresh_sanctions_lists,
        health_check,
    )
    
    assert sla_sweep is not None
    assert recompute_behavioral_baselines is not None
    assert process_pending_dsar_requests is not None
    assert verify_audit_chain_integrity is not None
    assert send_filing_reminders is not None
    assert refresh_sanctions_lists is not None
    assert health_check is not None
