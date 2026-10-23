"""Evaluation harness for compliance pipeline with labelled scenarios."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.compliance_engine import ComplianceEngine
from app.models import ScreeningResult, TransactionRequest


@dataclass
class LabelledScenario:
    """A test scenario with expected outcomes."""
    id: str
    description: str
    transaction: dict
    expected_status: str  # approved, flagged, blocked, in_review
    expected_rules_triggered: list[str] = field(default_factory=list)
    expected_behavioral_range: tuple[float, float] | None = None  # (min, max)
    tags: list[str] = field(default_factory=list)  # e.g., ["sanctions", "high_risk"]


@dataclass
class StageMetrics:
    """Precision/recall/FPR for a single stage."""
    stage_name: str
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)."""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)."""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def fpr(self) -> float:
        """False Positive Rate = FP / (FP + TN)."""
        if self.false_positives + self.true_negatives == 0:
            return 0.0
        return self.false_positives / (self.false_positives + self.true_negatives)

    @property
    def f1_score(self) -> float:
        """F1 = 2 * (precision * recall) / (precision + recall)."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)


@dataclass
class EvalReport:
    """Evaluation report with per-stage metrics."""
    timestamp: str
    total_scenarios: int
    passed: int
    failed: int
    stage_metrics: dict[str, StageMetrics] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "accuracy": self.passed / max(self.total_scenarios, 1),
            "stage_metrics": {
                name: {
                    "precision": round(m.precision, 3),
                    "recall": round(m.recall, 3),
                    "fpr": round(m.fpr, 3),
                    "f1_score": round(m.f1_score, 3),
                    "tp": m.true_positives,
                    "fp": m.false_positives,
                    "tn": m.true_negatives,
                    "fn": m.false_negatives,
                }
                for name, m in self.stage_metrics.items()
            },
            "failures": self.failures[:10],  # Limit to first 10 failures
        }


class EvalHarness:
    """Evaluation harness for compliance pipeline."""

    def __init__(self, scenarios_path: Path | None = None):
        self.scenarios_path = scenarios_path or Path(__file__).parent / "scenarios.json"
        self.engine = ComplianceEngine()

    def load_scenarios(self) -> list[LabelledScenario]:
        """Load labelled scenarios from JSON file."""
        if not self.scenarios_path.exists():
            return self._default_scenarios()

        with open(self.scenarios_path, "r") as f:
            data = json.load(f)

        return [
            LabelledScenario(
                id=s["id"],
                description=s["description"],
                transaction=s["transaction"],
                expected_status=s["expected_status"],
                expected_rules_triggered=s.get("expected_rules_triggered", []),
                expected_behavioral_range=tuple(s["expected_behavioral_range"]) if s.get("expected_behavioral_range") else None,
                tags=s.get("tags", []),
            )
            for s in data
        ]

    def _default_scenarios(self) -> list[LabelledScenario]:
        """Default labelled scenarios for testing."""
        return [
            LabelledScenario(
                id="clean-small",
                description="Clean small transaction should be approved",
                transaction={
                    "amount": 100.0,
                    "transaction_type": "ach",
                    "sender_name": "John Doe",
                    "receiver_name": "Jane Smith",
                },
                expected_status="approved",
                tags=["clean", "low_risk"],
            ),
            LabelledScenario(
                id="sanctioned-sender",
                description="Sanctioned sender should be blocked",
                transaction={
                    "amount": 5000.0,
                    "transaction_type": "wire",
                    "sender_name": "darkfund",  # In fallback sanctions list
                    "receiver_name": "Anyone",
                },
                expected_status="blocked",
                expected_rules_triggered=["RULE-001"],
                tags=["sanctions", "high_risk"],
            ),
            LabelledScenario(
                id="high-risk-country",
                description="Transaction to high-risk country should be escalated",
                transaction={
                    "amount": 10000.0,
                    "transaction_type": "international",
                    "sender_name": "Regular Corp",
                    "receiver_name": "Foreign Entity",
                    "destination_country": "KP",  # North Korea
                },
                expected_status="blocked",
                expected_rules_triggered=["RULE-004"],
                tags=["geography", "high_risk"],
            ),
            LabelledScenario(
                id="threshold-exceeded",
                description="Large transaction should trigger threshold rule",
                transaction={
                    "amount": 15000.0,
                    "transaction_type": "wire",
                    "sender_name": "Big Corp",
                    "receiver_name": "Supplier",
                },
                expected_status="in_review",
                expected_rules_triggered=["RULE-003"],
                tags=["threshold", "medium_risk"],
            ),
        ]

    def run_evaluation(self, db: Session | None = None) -> EvalReport:
        """Run evaluation against all labelled scenarios."""
        scenarios = self.load_scenarios()
        report = EvalReport(
            timestamp=datetime.utcnow().isoformat(),
            total_scenarios=len(scenarios),
            passed=0,
            failed=0,
        )

        # Initialize stage metrics
        report.stage_metrics["sanctions"] = StageMetrics("sanctions")
        report.stage_metrics["pep"] = StageMetrics("pep")
        report.stage_metrics["threshold"] = StageMetrics("threshold")
        report.stage_metrics["geography"] = StageMetrics("geography")
        report.stage_metrics["overall"] = StageMetrics("overall")

        for scenario in scenarios:
            try:
                # Create transaction request
                tx = TransactionRequest(**scenario.transaction)

                # Run screening
                result = self.engine.screen(tx, db=db)

                # Check if scenario passed
                passed = self._check_scenario(scenario, result)

                if passed:
                    report.passed += 1
                else:
                    report.failed += 1
                    report.failures.append({
                        "scenario_id": scenario.id,
                        "description": scenario.description,
                        "expected_status": scenario.expected_status,
                        "actual_status": result.status.value,
                        "rules_triggered": [r.rule_id for r in result.rule_results if r.triggered],
                    })

                # Update stage metrics
                self._update_stage_metrics(scenario, result, report.stage_metrics)

            except Exception as e:
                report.failed += 1
                report.failures.append({
                    "scenario_id": scenario.id,
                    "description": scenario.description,
                    "error": str(e),
                })

        return report

    def _check_scenario(self, scenario: LabelledScenario, result: ScreeningResult) -> bool:
        """Check if a scenario passed."""
        # Check status
        if result.status.value != scenario.expected_status:
            return False

        # Check expected rules triggered
        triggered_rules = {r.rule_id for r in result.rule_results if r.triggered}
        expected_rules = set(scenario.expected_rules_triggered)
        if triggered_rules != expected_rules:
            return False

        # Check behavioral range if specified
        if scenario.expected_behavioral_range and result.behavioral_score is not None:
            min_val, max_val = scenario.expected_behavioral_range
            if not (min_val <= result.behavioral_score <= max_val):
                return False

        return True

    def _update_stage_metrics(
        self,
        scenario: LabelledScenario,
        result: ScreeningResult,
        metrics: dict[str, StageMetrics],
    ):
        """Update stage metrics based on scenario results."""
        triggered_rules = {r.rule_id for r in result.rule_results if r.triggered}

        # Sanctions stage
        if "sanctions" in scenario.tags:
            if "RULE-001" in triggered_rules:
                metrics["sanctions"].true_positives += 1
            else:
                metrics["sanctions"].false_negatives += 1
        else:
            if "RULE-001" in triggered_rules:
                metrics["sanctions"].false_positives += 1
            else:
                metrics["sanctions"].true_negatives += 1

        # PEP stage
        if "pep" in scenario.tags:
            if "RULE-002" in triggered_rules:
                metrics["pep"].true_positives += 1
            else:
                metrics["pep"].false_negatives += 1
        else:
            if "RULE-002" in triggered_rules:
                metrics["pep"].false_positives += 1
            else:
                metrics["pep"].true_negatives += 1

        # Threshold stage
        if "threshold" in scenario.tags:
            if "RULE-003" in triggered_rules:
                metrics["threshold"].true_positives += 1
            else:
                metrics["threshold"].false_negatives += 1
        else:
            if "RULE-003" in triggered_rules:
                metrics["threshold"].false_positives += 1
            else:
                metrics["threshold"].true_negatives += 1

        # Geography stage
        if "geography" in scenario.tags:
            if "RULE-004" in triggered_rules:
                metrics["geography"].true_positives += 1
            else:
                metrics["geography"].false_negatives += 1
        else:
            if "RULE-004" in triggered_rules:
                metrics["geography"].false_positives += 1
            else:
                metrics["geography"].true_negatives += 1

        # Overall stage
        if result.status.value == scenario.expected_status:
            metrics["overall"].true_positives += 1
        else:
            metrics["overall"].false_negatives += 1
