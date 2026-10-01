"""
FinShield AI — Core Compliance Engine
7-stage pipeline: Ingest → Validate → Rule Screen → Behavioral → ML Classify → Risk Score → Decision
"""
from __future__ import annotations

import random
import time
import uuid
from datetime import datetime

from app.models import (
    CreditTier,
    RuleResult,
    RuleType,
    ScreeningResult,
    ScreeningStatus,
    TransactionRequest,
)

# --- Simulated sanctions / PEP lists ---
SANCTIONED_ENTITIES = {"globalremit", "darkfund", "terrorfin"}
PEP_ENTITIES = {"senator xyz", "minister abc", "ambassador qrs"}
HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "CU", "RU"}
THRESHOLD_WIRE = 10000.0
THRESHOLD_INTERNATIONAL = 50000.0
VELOCITY_WINDOW_TXS = 5


class ComplianceEngine:
    """
    The core 7-stage compliance pipeline.
    Each stage is a separate method for clarity and testability.
    """

    def __init__(self) -> None:
        self._idempotency_cache: dict[str, ScreeningResult] = {}

    @staticmethod
    def rule_definitions() -> list[dict]:
        """Expose the hard-rule definitions for the Rules management UI.

        `parameters` = genuinely user-editable (the engine reads these).
        `metadata`   = read-only display info (the engine does NOT accept overrides here).
        """
        return [
            {
                "rule_id": "RULE-001",
                "rule_type": "sanctions",
                "name": "OFAC Sanctions List Match",
                "description": "Blocks transactions where the sender or receiver matches a known sanctions entity.",
                "enabled": True,
                "action": "block",
                "parameters": {},
                "metadata": {"list_size": len(SANCTIONED_ENTITIES), "editable": False},
            },
            {
                "rule_id": "RULE-002",
                "rule_type": "pep",
                "name": "Politically Exposed Person Check",
                "description": "Flags transactions involving politically exposed persons for enhanced due diligence.",
                "enabled": True,
                "action": "flag",
                "parameters": {},
                "metadata": {"list_size": len(PEP_ENTITIES), "editable": False},
            },
            {
                "rule_id": "RULE-003",
                "rule_type": "threshold",
                "name": "Amount Threshold",
                "description": "Reviews transactions that exceed reporting thresholds for their type.",
                "enabled": True,
                "action": "review",
                "parameters": {"wire": THRESHOLD_WIRE, "international": THRESHOLD_INTERNATIONAL},
                "metadata": {"editable": True},
            },
            {
                "rule_id": "RULE-004",
                "rule_type": "geography",
                "name": "High-Risk Country Check",
                "description": "Blocks transactions destined for embargoed or high-risk jurisdictions.",
                "enabled": True,
                "action": "escalate",
                "parameters": {"countries": sorted(HIGH_RISK_COUNTRIES)},
                "metadata": {"editable": True},
            },
        ]

    def screen(self, tx: TransactionRequest, rule_configs: dict[str, dict] | None = None) -> ScreeningResult:
        """Run the full compliance pipeline on a transaction.

        rule_configs: optional per-user overrides keyed by rule_id, each value
        a dict like {"enabled": bool, "custom_parameters": {...}}. Disabled rules
        are skipped; custom parameters override defaults.
        """
        rule_configs = rule_configs or {}
        pipeline_start = time.monotonic()
        stages: list[str] = []

        # Stage 1: Idempotency check
        if tx.idempotency_key in self._idempotency_cache:
            return self._idempotency_cache[tx.idempotency_key]
        stages.append("idempotency_check")

        # Stage 2: Input validation (already done by Pydantic)
        stages.append("validation")

        # Stage 3: Hard rule engine (respects user rule configs)
        rule_results, rule_latency = self._run_rules(tx, rule_configs)
        stages.append("rule_engine")
        any_rule_triggered = any(r.triggered for r in rule_results)

        # Determine credit tier based on pipeline depth needed
        credit_tier = self._determine_tier(tx, any_rule_triggered, rule_configs)
        credits = {
            CreditTier.RULE_ONLY: 0.2,
            CreditTier.BEHAVIORAL: 0.5,
            CreditTier.FULL_ML: 1.0,
        }[credit_tier]

        # Stage 4: Behavioral analysis (if warranted)
        behavioral_score = None
        if credit_tier in (CreditTier.BEHAVIORAL, CreditTier.FULL_ML):
            behavioral_score = self._behavioral_score(tx)
            stages.append("behavioral_analysis")

        # Stage 5: ML classification (if warranted)
        ml_class = None
        ml_conf = None
        if credit_tier == CreditTier.FULL_ML:
            ml_class, ml_conf = self._ml_classify(tx, behavioral_score or 0)
            stages.append("ml_classification")

        # Stage 6: Risk scoring
        risk_score = self._compute_risk(
            tx, rule_results, behavioral_score, ml_conf
        )
        stages.append("risk_scoring")

        # Stage 7: Decision (respects triggered rule actions)
        status = self._make_decision(risk_score, any_rule_triggered, tx, rule_results)
        stages.append("decision")

        total_latency = (time.monotonic() - pipeline_start) * 1000

        result = ScreeningResult(
            transaction_id=f"TX-{random.randint(10000, 99999)}",
            idempotency_key=tx.idempotency_key,
            status=status,
            risk_score=round(risk_score, 4),
            credit_tier=credit_tier,
            credits_consumed=credits,
            rule_results=rule_results,
            behavioral_score=round(behavioral_score, 4) if behavioral_score is not None else None,
            ml_classification=ml_class,
            ml_confidence=round(ml_conf, 4) if ml_conf is not None else None,
            total_latency_ms=round(total_latency, 2),
            pipeline_stages=stages,
        )

        self._idempotency_cache[tx.idempotency_key] = result
        return result

    # --- Stage 3: Rule Engine ---
    def _run_rules(self, tx: TransactionRequest, rule_configs: dict[str, dict] | None = None) -> tuple[list[RuleResult], float]:
        rule_configs = rule_configs or {}

        def is_enabled(rule_id: str, default: bool = True) -> bool:
            cfg = rule_configs.get(rule_id)
            if cfg and "enabled" in cfg:
                return bool(cfg["enabled"])
            return default

        def param(rule_id: str, key: str, default):
            cfg = rule_configs.get(rule_id) or {}
            cp = cfg.get("custom_parameters") or {}
            return cp.get(key, default)

        start = time.monotonic()
        results: list[RuleResult] = []

        # Sanctions check (RULE-001)
        s_start = time.monotonic()
        if is_enabled("RULE-001"):
            sender_sanctioned = tx.sender_name.lower() in SANCTIONED_ENTITIES
            results.append(RuleResult(
                rule_id="RULE-001",
                rule_type=RuleType.SANCTIONS,
                rule_name="OFAC Sanctions List Match",
                triggered=sender_sanctioned,
                detail=f"Sender '{tx.sender_name}' matched OFAC list" if sender_sanctioned else None,
                latency_ms=round((time.monotonic() - s_start) * 1000, 2),
            ))

        # PEP check (RULE-002)
        p_start = time.monotonic()
        if is_enabled("RULE-002"):
            pep_match = tx.sender_name.lower() in PEP_ENTITIES or tx.receiver_name.lower() in PEP_ENTITIES
            results.append(RuleResult(
                rule_id="RULE-002",
                rule_type=RuleType.PEP,
                rule_name="Politically Exposed Person Check",
                triggered=pep_match,
                detail="PEP match found" if pep_match else None,
                latency_ms=round((time.monotonic() - p_start) * 1000, 2),
            ))

        # Threshold check (RULE-003) — user can override wire/international thresholds
        t_start = time.monotonic()
        if is_enabled("RULE-003"):
            wire_thr = float(param("RULE-003", "wire", THRESHOLD_WIRE))
            intl_thr = float(param("RULE-003", "international", THRESHOLD_INTERNATIONAL))
            threshold = wire_thr if tx.transaction_type == "wire" else intl_thr
            threshold_exceeded = tx.amount >= threshold
            results.append(RuleResult(
                rule_id="RULE-003",
                rule_type=RuleType.THRESHOLD,
                rule_name=f"Amount Threshold (>${threshold:,.0f})",
                triggered=threshold_exceeded,
                detail=f"Amount ${tx.amount:,.2f} exceeds threshold ${threshold:,.2f}" if threshold_exceeded else None,
                latency_ms=round((time.monotonic() - t_start) * 1000, 2),
            ))

        # Geography check (RULE-004) — user can override country list
        g_start = time.monotonic()
        if is_enabled("RULE-004"):
            countries = param("RULE-004", "countries", sorted(HIGH_RISK_COUNTRIES))
            country_set = set(countries) if isinstance(countries, (list, tuple, set)) else HIGH_RISK_COUNTRIES
            high_risk_geo = tx.destination_country in country_set if tx.destination_country else False
            results.append(RuleResult(
                rule_id="RULE-004",
                rule_type=RuleType.GEOGRAPHY,
                rule_name="High-Risk Country Check",
                triggered=high_risk_geo,
                detail=f"Destination country {tx.destination_country} is high-risk" if high_risk_geo else None,
                latency_ms=round((time.monotonic() - g_start) * 1000, 2),
            ))

        latency = (time.monotonic() - start) * 1000
        return results, latency

    def evaluate_rule(self, rule_def: dict, tx_data: dict) -> dict:
        """Evaluate a single rule against transaction data (for simulation)."""
        rule_id = rule_def["rule_id"]
        
        # RULE-001: Sanctions
        if rule_id == "RULE-001":
            sender_sanctioned = tx_data.get("sender_name", "").lower() in SANCTIONED_ENTITIES
            return {"triggered": sender_sanctioned}
        
        # RULE-002: PEP
        if rule_id == "RULE-002":
            pep_match = (
                tx_data.get("sender_name", "").lower() in PEP_ENTITIES or
                tx_data.get("receiver_name", "").lower() in PEP_ENTITIES
            )
            return {"triggered": pep_match}
        
        # RULE-003: Threshold
        if rule_id == "RULE-003":
            params = rule_def.get("parameters", {})
            wire_thr = float(params.get("wire", THRESHOLD_WIRE))
            intl_thr = float(params.get("international", THRESHOLD_INTERNATIONAL))
            tx_type = tx_data.get("transaction_type", "")
            threshold = wire_thr if tx_type == "wire" else intl_thr
            amount = tx_data.get("amount", 0)
            return {"triggered": amount >= threshold}
        
        # RULE-004: Geography
        if rule_id == "RULE-004":
            params = rule_def.get("parameters", {})
            countries = params.get("countries", sorted(HIGH_RISK_COUNTRIES))
            country_set = set(countries) if isinstance(countries, (list, tuple, set)) else HIGH_RISK_COUNTRIES
            dest_country = tx_data.get("destination_country")
            high_risk = dest_country in country_set if dest_country else False
            return {"triggered": high_risk}
        
        return {"triggered": False}

    # --- Stage 4: Behavioral Analysis ---
    def _behavioral_score(self, tx: TransactionRequest) -> float:
        """Simulate behavioral scoring (0-1, higher = more suspicious)."""
        score = 0.0
        if tx.amount > 50000:
            score += 0.3
        elif tx.amount > 10000:
            score += 0.15
        if tx.transaction_type == "international":
            score += 0.1
        if tx.destination_country in HIGH_RISK_COUNTRIES:
            score += 0.25
        # Add some randomness to simulate ML inference
        score += random.uniform(0, 0.15)
        return min(score, 1.0)

    # --- Stage 5: ML Classification ---
    def _ml_classify(self, tx: TransactionRequest, behavioral: float) -> tuple[str, float]:
        """Simulate ML classification via RAG + LoRA."""
        if behavioral > 0.6:
            return "high_risk", min(0.7 + random.uniform(0, 0.25), 0.99)
        elif behavioral > 0.3:
            return "medium_risk", min(0.5 + random.uniform(0, 0.3), 0.85)
        else:
            return "low_risk", min(0.6 + random.uniform(0, 0.3), 0.95)

    # --- Stage 6: Risk Scoring ---
    def _compute_risk(
        self,
        tx: TransactionRequest,
        rules: list[RuleResult],
        behavioral: float | None,
        ml_conf: float | None,
    ) -> float:
        triggered_count = sum(1 for r in rules if r.triggered)
        rule_risk = min(triggered_count * 0.25, 1.0)

        score = rule_risk * 0.5
        if behavioral is not None:
            score += behavioral * 0.3
        else:
            score += 0.1  # baseline
        if ml_conf is not None:
            score += ml_conf * 0.2
        else:
            score += 0.05

        return min(score, 1.0)

    # --- Stage 7: Decision ---
    # Rule action enforcement: a triggered rule's declared action is authoritative.
    # block/escalate/flag/review map to concrete statuses and override the aggregate score.
    RULE_ACTIONS: dict[str, str] = {
        "RULE-001": "block",      # OFAC sanctions
        "RULE-002": "flag",       # PEP
        "RULE-003": "review",     # amount threshold
        "RULE-004": "escalate",   # high-risk geography
    }

    def _make_decision(self, risk: float, rules_triggered: bool, tx: TransactionRequest, rule_results: list[RuleResult] | None = None) -> ScreeningStatus:
        rule_results = rule_results or []
        fired_actions = {
            self.RULE_ACTIONS.get(r.rule_id)
            for r in rule_results if r.triggered
        }
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
        if risk >= 0.8 or (rules_triggered and risk >= 0.6):
            return ScreeningStatus.BLOCKED
        elif risk >= 0.5:
            return ScreeningStatus.FLAGGED
        elif risk >= 0.3:
            return ScreeningStatus.IN_REVIEW
        return ScreeningStatus.APPROVED

    # --- Credit Tier Determination ---
    def _determine_tier(self, tx: TransactionRequest, rules_triggered: bool, rule_configs: dict[str, dict] | None = None) -> CreditTier:
        rule_configs = rule_configs or {}
        # Respect user's custom wire threshold when present
        try:
            wire_thr = float(((rule_configs.get("RULE-003") or {}).get("custom_parameters") or {}).get("wire", THRESHOLD_WIRE))
        except (TypeError, ValueError):
            wire_thr = THRESHOLD_WIRE
        try:
            countries = ((rule_configs.get("RULE-004") or {}).get("custom_parameters") or {}).get("countries", sorted(HIGH_RISK_COUNTRIES))
            country_set = set(countries) if isinstance(countries, (list, tuple, set)) else HIGH_RISK_COUNTRIES
        except Exception:
            country_set = HIGH_RISK_COUNTRIES
        if tx.amount >= wire_thr or (tx.destination_country in country_set if tx.destination_country else False):
            return CreditTier.FULL_ML
        if rules_triggered or tx.amount >= 5000:
            return CreditTier.BEHAVIORAL
        return CreditTier.RULE_ONLY
