"""Tests for evaluation harness (S2.7)."""

import pytest

from tests.eval_harness import EvalHarness, StageMetrics


class TestStageMetrics:
    """Test stage metrics calculations."""

    def test_precision_calculation(self):
        """Precision = TP / (TP + FP)."""
        m = StageMetrics("test", true_positives=8, false_positives=2)
        assert m.precision == 0.8

    def test_precision_zero_division(self):
        """Precision should be 0 when TP + FP = 0."""
        m = StageMetrics("test")
        assert m.precision == 0.0

    def test_recall_calculation(self):
        """Recall = TP / (TP + FN)."""
        m = StageMetrics("test", true_positives=8, false_negatives=2)
        assert m.recall == 0.8

    def test_recall_zero_division(self):
        """Recall should be 0 when TP + FN = 0."""
        m = StageMetrics("test")
        assert m.recall == 0.0

    def test_fpr_calculation(self):
        """FPR = FP / (FP + TN)."""
        m = StageMetrics("test", false_positives=2, true_negatives=8)
        assert m.fpr == 0.2

    def test_fpr_zero_division(self):
        """FPR should be 0 when FP + TN = 0."""
        m = StageMetrics("test")
        assert m.fpr == 0.0

    def test_f1_score_calculation(self):
        """F1 = 2 * (precision * recall) / (precision + recall)."""
        m = StageMetrics("test", true_positives=8, false_positives=2, false_negatives=2)
        # precision = 0.8, recall = 0.8, F1 = 0.8
        assert abs(m.f1_score - 0.8) < 0.01

    def test_f1_score_zero_division(self):
        """F1 should be 0 when precision + recall = 0."""
        m = StageMetrics("test")
        assert m.f1_score == 0.0


class TestEvalHarness:
    """Test evaluation harness."""

    def test_load_default_scenarios(self):
        """Should load default scenarios when file doesn't exist."""
        harness = EvalHarness()
        scenarios = harness.load_scenarios()
        assert len(scenarios) > 0
        assert all(s.id for s in scenarios)
        assert all(s.expected_status for s in scenarios)

    def test_run_evaluation(self):
        """Should run evaluation and return report."""
        harness = EvalHarness()
        report = harness.run_evaluation()

        assert report.total_scenarios > 0
        assert report.passed + report.failed == report.total_scenarios
        assert "overall" in report.stage_metrics
        assert "sanctions" in report.stage_metrics

    def test_evaluation_report_serialization(self):
        """Should serialize report to dictionary."""
        harness = EvalHarness()
        report = harness.run_evaluation()
        report_dict = report.to_dict()

        assert "timestamp" in report_dict
        assert "total_scenarios" in report_dict
        assert "accuracy" in report_dict
        assert "stage_metrics" in report_dict
        assert "failures" in report_dict

    def test_clean_transaction_passes(self):
        """Clean transaction scenario should pass."""
        harness = EvalHarness()
        scenarios = harness.load_scenarios()
        clean_scenario = next(s for s in scenarios if s.id == "clean-small")

        from app.models import TransactionRequest
        from app.compliance_engine import ComplianceEngine

        tx = TransactionRequest(**clean_scenario.transaction)
        engine = ComplianceEngine()
        result = engine.screen(tx)

        assert result.status.value == clean_scenario.expected_status

    def test_sanctioned_transaction_blocked(self):
        """Sanctioned sender scenario should be blocked."""
        harness = EvalHarness()
        scenarios = harness.load_scenarios()
        sanctioned_scenario = next(s for s in scenarios if s.id == "sanctioned-sender")

        from app.models import TransactionRequest
        from app.compliance_engine import ComplianceEngine

        tx = TransactionRequest(**sanctioned_scenario.transaction)
        engine = ComplianceEngine()
        result = engine.screen(tx)

        assert result.status.value == "blocked"
        triggered_rules = {r.rule_id for r in result.rule_results if r.triggered}
        assert "RULE-001" in triggered_rules

    def test_high_risk_country_blocked(self):
        """High-risk country scenario should be blocked."""
        harness = EvalHarness()
        scenarios = harness.load_scenarios()
        geo_scenario = next(s for s in scenarios if s.id == "high-risk-country")

        from app.models import TransactionRequest
        from app.compliance_engine import ComplianceEngine

        tx = TransactionRequest(**geo_scenario.transaction)
        engine = ComplianceEngine()
        result = engine.screen(tx)

        assert result.status.value == "blocked"
        triggered_rules = {r.rule_id for r in result.rule_results if r.triggered}
        assert "RULE-004" in triggered_rules
