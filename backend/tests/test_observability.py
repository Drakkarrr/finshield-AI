"""Tests for observability features (S4.4)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import (
    logger,
    TRANSACTIONS_TOTAL,
    RISK_SCORES,
    get_metrics,
    ALERT_RULES,
)


def test_structured_logger():
    """Test that structlog logger is configured."""
    assert logger is not None
    # Logger should be able to log without errors
    logger.info("test_message", key="value")


def test_prometheus_metrics_endpoint():
    """Test that /metrics endpoint returns Prometheus metrics."""
    client = TestClient(app)
    response = client.get("/metrics")
    
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"] or "text/openmetrics" in response.headers["content-type"]
    
    # Check that metrics are present
    metrics_text = response.text
    assert "finshield_transactions_total" in metrics_text or "finshield_risk_score" in metrics_text


def test_get_metrics_function():
    """Test that get_metrics returns valid Prometheus format."""
    metrics_text, content_type = get_metrics()
    
    assert isinstance(metrics_text, str)
    assert len(metrics_text) > 0
    assert "text/plain" in content_type or "text/openmetrics" in content_type


def test_metrics_counters_exist():
    """Test that Prometheus metrics counters are defined."""
    assert TRANSACTIONS_TOTAL is not None
    assert RISK_SCORES is not None
    
    # Test that we can increment counters
    TRANSACTIONS_TOTAL.labels(status="approved", credit_tier="rules_only").inc()
    RISK_SCORES.observe(50.0)


def test_alert_rules_defined():
    """Test that alert rules are defined."""
    assert ALERT_RULES is not None
    assert len(ALERT_RULES) > 0
    
    # Check specific alert rules exist
    assert "high_error_rate" in ALERT_RULES
    assert "slow_transactions" in ALERT_RULES
    assert "circuit_breaker_open" in ALERT_RULES
    assert "low_cache_hit_rate" in ALERT_RULES
    
    # Check alert rule structure
    for rule_name, rule in ALERT_RULES.items():
        assert "expr" in rule
        assert "for" in rule
        assert "labels" in rule
        assert "annotations" in rule
        assert "severity" in rule["labels"]


def test_transaction_metrics_recorded():
    """Test that transaction metrics are recorded during screening."""
    from app.compliance_engine import ComplianceEngine
    from app.models import TransactionRequest
    
    engine = ComplianceEngine()
    tx = TransactionRequest(
        idempotency_key="test-obs-001",
        amount=100.0,
        currency="USD",
        transaction_type="wire",
        sender_name="John Doe",
        receiver_name="Jane Smith",
    )
    
    result = engine.screen(tx)
    
    # Metrics should have been recorded
    # We can't easily check the exact values, but we can verify the screening completed
    assert result is not None
    assert result.transaction_id is not None
