"""Decision gate.

1. The rule-action precedence gate decides first. Its semantics are pinned by tests and must not
   change: a triggered rule's declared action is authoritative and overrides the score.
2. Escalation overlays can only RAISE severity, never lower it:
   - a behavioral trigger, or a RAG sanctions match, raises to at least FLAGGED;
   - a failed configured dependency (degraded) raises to at least IN_REVIEW, so a degraded
     pipeline never auto-approves (Wiki §8).
   RAG and behavioral evidence are deliberately not allowed to lower a decision: similarity to a
   precedent or a quiet account history is not grounds to clear a hit from a hard control.
"""
from __future__ import annotations

from app.models import Reason, RuleResult, ScreeningStatus

# Rule action enforcement: a triggered rule's declared action is authoritative.
RULE_ACTIONS: dict[str, str] = {
    "RULE-001": "block",      # sanctions
    "RULE-002": "flag",       # PEP
    "RULE-003": "review",     # amount threshold
    "RULE-004": "escalate",   # high-risk geography
}

SEVERITY = {ScreeningStatus.APPROVED: 0, ScreeningStatus.IN_REVIEW: 1, ScreeningStatus.FLAGGED: 2,
            ScreeningStatus.BLOCKED: 3}


def precedence_gate(risk: float, rules_triggered: bool, rule_results: list[RuleResult], bands: dict) -> ScreeningStatus:
    fired_actions = {RULE_ACTIONS.get(r.rule_id) for r in rule_results if r.triggered}
    # A triggered hard control with a mandatory action overrides the risk score.
    if "block" in fired_actions:
        return ScreeningStatus.BLOCKED
    if "escalate" in fired_actions:
        return ScreeningStatus.BLOCKED
    if "flag" in fired_actions:
        return ScreeningStatus.FLAGGED
    if "review" in fired_actions:
        return ScreeningStatus.IN_REVIEW
    # Fall back to score-based decision when no rule action fired.
    if risk >= bands["block"] or (rules_triggered and risk >= bands["block_if_rule"]):
        return ScreeningStatus.BLOCKED
    elif risk >= bands["flag"]:
        return ScreeningStatus.FLAGGED
    elif risk >= bands["review"]:
        return ScreeningStatus.IN_REVIEW
    return ScreeningStatus.APPROVED


def escalate(status: ScreeningStatus, floor: ScreeningStatus) -> ScreeningStatus:
    return floor if SEVERITY[floor] > SEVERITY[status] else status


def decide(
    risk: float,
    rule_results: list[RuleResult],
    bands: dict,
    behavioral_triggered: bool,
    rag_sanctions_match: bool,
    degraded_dependencies: list[str],
) -> tuple[ScreeningStatus, list[Reason]]:
    any_triggered = any(r.triggered for r in rule_results)
    status = precedence_gate(risk, any_triggered, rule_results, bands)
    fired = sorted(r.rule_id for r in rule_results if r.triggered)
    reasons = [Reason(source="gate", feature="rule_action" if fired else "score_band", value=status.value,
                      rules=fired, risk_score=round(risk, 4))]
    for cond, floor, feature in (
        (behavioral_triggered, ScreeningStatus.FLAGGED, "behavioral_trigger"),
        (rag_sanctions_match, ScreeningStatus.FLAGGED, "rag_sanctions_match"),
        (bool(degraded_dependencies), ScreeningStatus.IN_REVIEW, "degraded_dependency"),
    ):
        if cond:
            raised = escalate(status, floor)
            if raised != status:
                reasons.append(Reason(source="gate", feature=feature, value=raised.value, previous=status.value,
                                      dependencies=degraded_dependencies or None))
            status = raised
    return status, reasons
