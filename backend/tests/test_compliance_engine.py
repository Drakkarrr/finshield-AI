"""
FinShield AI — Unit Tests for Compliance Engine
Tests the 7-stage pipeline: rules, behavioral, ML, risk scoring, decisions.
"""
import pytest

from app.compliance_engine import ComplianceEngine
from app.models import (
    CreditTier,
    ScreeningStatus,
    TransactionRequest,
    TransactionType,
)


@pytest.fixture
def engine():
    return ComplianceEngine()


# --- Helper to build transactions ---
def make_tx(**overrides) -> TransactionRequest:
    defaults = dict(
        amount=1000.0,
        currency="USD",
        transaction_type=TransactionType.WIRE,
        sender_name="John Doe",
        receiver_name="Jane Smith",
    )
    defaults.update(overrides)
    return TransactionRequest(**defaults)


# =============================================
# Stage 3: Rule Engine Tests
# =============================================

class TestRuleEngine:
    def test_sanctions_match_triggers_rule(self, engine):
        tx = make_tx(sender_name="GlobalRemit")
        result = engine.screen(tx)
        sanctions_rules = [r for r in result.rule_results if r.rule_type == "sanctions"]
        assert len(sanctions_rules) == 1
        assert sanctions_rules[0].triggered is True

    def test_clean_sender_no_sanctions(self, engine):
        tx = make_tx(sender_name="Normal Corp")
        result = engine.screen(tx)
        sanctions_rules = [r for r in result.rule_results if r.rule_type == "sanctions"]
        assert sanctions_rules[0].triggered is False

    def test_pep_match_triggers(self, engine):
        tx = make_tx(sender_name="Senator XYZ")
        result = engine.screen(tx)
        pep_rules = [r for r in result.rule_results if r.rule_type == "pep"]
        assert pep_rules[0].triggered is True

    def test_threshold_exceeded_for_wire(self, engine):
        tx = make_tx(amount=15000.0, transaction_type=TransactionType.WIRE)
        result = engine.screen(tx)
        threshold_rules = [r for r in result.rule_results if r.rule_type == "threshold"]
        assert threshold_rules[0].triggered is True

    def test_threshold_not_exceeded_for_small_amount(self, engine):
        tx = make_tx(amount=500.0, transaction_type=TransactionType.WIRE)
        result = engine.screen(tx)
        threshold_rules = [r for r in result.rule_results if r.rule_type == "threshold"]
        assert threshold_rules[0].triggered is False

    def test_high_risk_country_triggers(self, engine):
        tx = make_tx(destination_country="KP")
        result = engine.screen(tx)
        geo_rules = [r for r in result.rule_results if r.rule_type == "geography"]
        assert geo_rules[0].triggered is True

    def test_safe_country_no_trigger(self, engine):
        tx = make_tx(destination_country="US")
        result = engine.screen(tx)
        geo_rules = [r for r in result.rule_results if r.rule_type == "geography"]
        assert geo_rules[0].triggered is False


# =============================================
# Credit Tier Tests
# =============================================

class TestCreditTiers:
    def test_small_clean_tx_is_rule_only(self, engine):
        tx = make_tx(amount=100.0)
        result = engine.screen(tx)
        assert result.credit_tier == CreditTier.RULE_ONLY
        assert result.credits_consumed == 0.2

    def test_medium_amount_triggers_behavioral(self, engine):
        tx = make_tx(amount=8000.0)
        result = engine.screen(tx)
        assert result.credit_tier in (CreditTier.BEHAVIORAL, CreditTier.FULL_ML)

    def test_high_risk_country_triggers_full_ml(self, engine):
        tx = make_tx(amount=500.0, destination_country="IR")
        result = engine.screen(tx)
        assert result.credit_tier == CreditTier.FULL_ML
        assert result.credits_consumed == 1.0

    def test_large_wire_triggers_full_ml(self, engine):
        tx = make_tx(amount=50000.0, transaction_type=TransactionType.WIRE)
        result = engine.screen(tx)
        assert result.credit_tier == CreditTier.FULL_ML


# =============================================
# Pipeline Stage Tests
# =============================================

class TestPipeline:
    def test_pipeline_includes_all_stages(self, engine):
        tx = make_tx(amount=60000.0, destination_country="SY")
        result = engine.screen(tx)
        assert "idempotency_check" in result.pipeline_stages
        assert "validation" in result.pipeline_stages
        assert "rule_engine" in result.pipeline_stages
        assert "risk_scoring" in result.pipeline_stages
        assert "decision" in result.pipeline_stages

    def test_rule_only_pipeline_shorter(self, engine):
        tx = make_tx(amount=100.0)
        result = engine.screen(tx)
        assert "ml_classification" not in result.pipeline_stages
        assert "behavioral_analysis" not in result.pipeline_stages

    def test_full_pipeline_includes_ml(self, engine):
        tx = make_tx(amount=60000.0, destination_country="KP")
        result = engine.screen(tx)
        assert "ml_classification" in result.pipeline_stages
        assert "behavioral_analysis" in result.pipeline_stages
        assert result.ml_classification is not None
        assert result.ml_confidence is not None


# =============================================
# Decision Tests
# =============================================

class TestDecisions:
    def test_clean_tx_approved(self, engine):
        tx = make_tx(amount=100.0)
        result = engine.screen(tx)
        assert result.status == ScreeningStatus.APPROVED

    def test_sanctioned_sender_blocked(self, engine):
        tx = make_tx(
            sender_name="GlobalRemit",
            amount=100000.0,
            transaction_type=TransactionType.INTERNATIONAL,
            destination_country="KP",
        )
        result = engine.screen(tx)
        assert result.status == ScreeningStatus.BLOCKED

    def test_risk_score_between_0_and_1(self, engine):
        for amount in [100, 5000, 50000, 200000]:
            tx = make_tx(amount=float(amount))
            result = engine.screen(tx)
            assert 0 <= result.risk_score <= 1

    def test_latency_is_positive(self, engine):
        tx = make_tx()
        result = engine.screen(tx)
        assert result.total_latency_ms >= 0


# =============================================
# Idempotency Tests
# =============================================

class TestIdempotency:
    def test_same_idempotency_key_returns_same_result(self, engine):
        tx1 = make_tx(amount=1000.0)
        tx1.idempotency_key = "test-key-123"
        result1 = engine.screen(tx1)

        tx2 = make_tx(amount=2000.0)
        tx2.idempotency_key = "test-key-123"
        result2 = engine.screen(tx2)

        assert result1.transaction_id == result2.transaction_id
        assert result1.status == result2.status
        assert result1.risk_score == result2.risk_score

    def test_different_idempotency_keys_different_results(self, engine):
        tx1 = make_tx(amount=1000.0)
        tx1.idempotency_key = "key-a"
        result1 = engine.screen(tx1)

        tx2 = make_tx(amount=1000.0)
        tx2.idempotency_key = "key-b"
        result2 = engine.screen(tx2)

        # Different keys should produce different transaction IDs
        assert result1.transaction_id != result2.transaction_id


# =============================================
# Rule Result Structure Tests
# =============================================

class TestRuleResultStructure:
    def test_all_four_rules_always_run(self, engine):
        tx = make_tx()
        result = engine.screen(tx)
        rule_types = {r.rule_type for r in result.rule_results}
        assert "sanctions" in rule_types
        assert "pep" in rule_types
        assert "threshold" in rule_types
        assert "geography" in rule_types

    def test_each_rule_has_latency(self, engine):
        tx = make_tx()
        result = engine.screen(tx)
        for rule in result.rule_results:
            assert rule.latency_ms >= 0
            assert rule.rule_id is not None
            assert rule.rule_name is not None
