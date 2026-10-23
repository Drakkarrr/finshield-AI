"""
FinShield AI — Core Compliance Engine
7-stage pipeline: Ingest → Validate → Rule Screen → Behavioral → ML Classify → Risk Score → Decision
"""
from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from app.config_service import ScreeningConfig
from app.domain.behavioral import score_behavioral
from app.domain.lists import DBListProvider
from app.models import (
    CreditTier,
    RuleResult,
    RuleType,
    ScreeningResult,
    ScreeningStatus,
    TransactionRequest,
)
from app.observability import (
    TRANSACTION_DURATION,
    SCREENING_PIPELINE_DURATION,
    RISK_SCORES,
    TRANSACTIONS_TOTAL,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# --- Fallback lists (used when DB not available) ---
SANCTIONED_ENTITIES = {"globalremit", "darkfund", "terrorfin"}
PEP_ENTITIES = {"senator xyz", "minister abc", "ambassador qrs"}
HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "CU", "RU"}
DEFAULT_RULE_PRIORITY = 100  # lower runs first; ties break on rule_id


class ComplianceEngine:
    """
    The core 7-stage compliance pipeline.
    Each stage is a separate method for clarity and testability.
    """

    @staticmethod
    def rule_definitions(config: ScreeningConfig | None = None) -> list[dict]:
        """Expose the hard-rule definitions for the Rules management UI.

        `parameters` = genuinely user-editable (the engine reads these).
        `metadata`   = read-only display info (the engine does NOT accept overrides here).
        """
        config = config or ScreeningConfig.defaults()
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
                "parameters": {"wire": config.threshold_wire, "international": config.threshold_international},
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

    def screen(
        self,
        tx: TransactionRequest,
        rule_configs: dict[str, dict] | None = None,
        config: ScreeningConfig | None = None,
        db: Session | None = None,
        user_id: str | None = None,
    ) -> ScreeningResult:
        """Run the full compliance pipeline on a transaction.

        rule_configs: per-user overrides keyed by rule_id ({"enabled", "custom_parameters",
        "priority"}), already filtered to those inside their effective window by the caller.
        config: runtime settings/flags (thresholds, weights, bands, credit cost, stage flags).
        """
        rule_configs = rule_configs or {}
        config = config or ScreeningConfig.defaults()
        pipeline_start = time.monotonic()
        stages: list[str] = []

        # Stage 1: Idempotency check (handled at API layer via Transaction.idempotency_key)
        stages.append("idempotency_check")

        # Stage 2: Input validation (already done by Pydantic)
        stages.append("validation")

        # Stage 3: Hard rule engine (respects user rule configs)
        rule_results, rule_latency = self._run_rules(tx, rule_configs, config, db)
        stages.append("rule_engine")
        any_rule_triggered = any(r.triggered for r in rule_results)

        # Determine credit tier based on pipeline depth needed
        credit_tier = self._determine_tier(tx, any_rule_triggered, rule_configs, config)
        credits = float(config.credit_cost[credit_tier.value])

        # Stage 4: Behavioral analysis (if warranted)
        behavioral_score = None
        behavioral_reasons = None
        if config.behavioral_enabled and credit_tier in (CreditTier.BEHAVIORAL, CreditTier.FULL_ML):
            behavioral_score, behavioral_reasons = self._behavioral_score(tx, db, user_id, config)
            stages.append("behavioral_analysis")

        # Stage 5: ML classification (if warranted)
        ml_class = None
        ml_conf = None
        if config.ml_enabled and credit_tier == CreditTier.FULL_ML:
            ml_class, ml_conf = self._ml_classify(tx, behavioral_score or 0)
            stages.append("ml_classification")

        # Stage 6: Risk scoring
        risk_score = self._compute_risk(tx, rule_results, behavioral_score, ml_conf, config.weights)
        stages.append("risk_scoring")

        # Stage 7: Decision (respects triggered rule actions)
        status = self._make_decision(risk_score, any_rule_triggered, tx, rule_results, config.bands)
        stages.append("decision")

        total_latency = (time.monotonic() - pipeline_start) * 1000

        # Record metrics (S4.4)
        TRANSACTION_DURATION.labels(stage="total").observe(total_latency / 1000)
        RISK_SCORES.observe(risk_score)
        TRANSACTIONS_TOTAL.labels(status=status.value, credit_tier=credit_tier.value).inc()

        result = ScreeningResult(
            transaction_id=f"TX-{hashlib.sha256(tx.idempotency_key.encode()).hexdigest()[:8]}",
            idempotency_key=tx.idempotency_key,
            status=status,
            risk_score=round(risk_score, 4),
            credit_tier=credit_tier,
            credits_consumed=credits,
            rule_results=rule_results,
            behavioral_score=round(behavioral_score, 4) if behavioral_score is not None else None,
            behavioral_reasons=behavioral_reasons,
            ml_classification=ml_class,
            ml_confidence=round(ml_conf, 4) if ml_conf is not None else None,
            total_latency_ms=round(total_latency, 2),
            pipeline_stages=stages,
        )

        return result

    # --- Stage 3: Rule Engine ---
    def _run_rules(
        self,
        tx: TransactionRequest,
        rule_configs: dict[str, dict] | None = None,
        config: ScreeningConfig | None = None,
        db: Session | None = None,
    ) -> tuple[list[RuleResult], float]:
        rule_configs = rule_configs or {}
        config = config or ScreeningConfig.defaults()

        def param(rule_id: str, key: str, default):
            cfg = rule_configs.get(rule_id) or {}
            cp = cfg.get("custom_parameters") or {}
            return cp.get(key, default)

        def sanctions() -> RuleResult:
            # Use DB-backed list provider if available and has data, otherwise fallback to hardcoded set
            if db is not None:
                from app.db_models import SanctionsEntry
                sanctions_count = db.query(SanctionsEntry).count()
                if sanctions_count > 0:
                    provider = DBListProvider(db)
                    matches = provider.check_sanctions(tx.sender_name, tx.destination_country)
                    if matches:
                        best_match = max(matches, key=lambda m: m.confidence)
                        return RuleResult(
                            rule_id="RULE-001",
                            rule_type=RuleType.SANCTIONS,
                            rule_name="OFAC Sanctions List Match",
                            triggered=True,
                            detail=f"Sender '{tx.sender_name}' matched sanctions list: {best_match.entity_name} ({best_match.match_type.value})",
                            latency_ms=0.0,
                            provenance=best_match.source_provenance,
                        )
                else:
                    # DB is empty, fall back to hardcoded list
                    sender_sanctioned = tx.sender_name.lower() in SANCTIONED_ENTITIES
                    if sender_sanctioned:
                        return RuleResult(
                            rule_id="RULE-001",
                            rule_type=RuleType.SANCTIONS,
                            rule_name="OFAC Sanctions List Match",
                            triggered=True,
                            detail=f"Sender '{tx.sender_name}' matched OFAC list",
                            latency_ms=0.0,
                            provenance="fallback:hardcoded",
                        )
            else:
                # No DB session, use hardcoded list
                sender_sanctioned = tx.sender_name.lower() in SANCTIONED_ENTITIES
                if sender_sanctioned:
                    return RuleResult(
                        rule_id="RULE-001",
                        rule_type=RuleType.SANCTIONS,
                        rule_name="OFAC Sanctions List Match",
                        triggered=True,
                        detail=f"Sender '{tx.sender_name}' matched OFAC list",
                        latency_ms=0.0,
                        provenance="fallback:hardcoded",
                    )
            return RuleResult(
                rule_id="RULE-001",
                rule_type=RuleType.SANCTIONS,
                rule_name="OFAC Sanctions List Match",
                triggered=False,
                latency_ms=0.0,
            )

        def pep() -> RuleResult:
            # Use DB-backed list provider if available and has data, otherwise fallback to hardcoded set
            if db is not None:
                from app.db_models import PEPEntry
                pep_count = db.query(PEPEntry).count()
                if pep_count > 0:
                    provider = DBListProvider(db)
                    sender_matches = provider.check_pep(tx.sender_name, tx.destination_country)
                    receiver_matches = provider.check_pep(tx.receiver_name, tx.destination_country)
                    all_matches = sender_matches + receiver_matches
                    if all_matches:
                        best_match = max(all_matches, key=lambda m: m.confidence)
                        matched_name = tx.sender_name if best_match in sender_matches else tx.receiver_name
                        return RuleResult(
                            rule_id="RULE-002",
                            rule_type=RuleType.PEP,
                            rule_name="Politically Exposed Person Check",
                            triggered=True,
                            detail=f"PEP match found: {matched_name} → {best_match.entity_name} ({best_match.match_type.value})",
                            latency_ms=0.0,
                            provenance=best_match.source_provenance,
                        )
                else:
                    # DB is empty, fall back to hardcoded list
                    pep_match = tx.sender_name.lower() in PEP_ENTITIES or tx.receiver_name.lower() in PEP_ENTITIES
                    if pep_match:
                        return RuleResult(
                            rule_id="RULE-002",
                            rule_type=RuleType.PEP,
                            rule_name="Politically Exposed Person Check",
                            triggered=True,
                            detail="PEP match found",
                            latency_ms=0.0,
                            provenance="fallback:hardcoded",
                        )
            else:
                # No DB session, use hardcoded list
                pep_match = tx.sender_name.lower() in PEP_ENTITIES or tx.receiver_name.lower() in PEP_ENTITIES
                if pep_match:
                    return RuleResult(
                        rule_id="RULE-002",
                        rule_type=RuleType.PEP,
                        rule_name="Politically Exposed Person Check",
                        triggered=True,
                        detail="PEP match found",
                        latency_ms=0.0,
                        provenance="fallback:hardcoded",
                    )
            return RuleResult(
                rule_id="RULE-002",
                rule_type=RuleType.PEP,
                rule_name="Politically Exposed Person Check",
                triggered=False,
                latency_ms=0.0,
            )

        def threshold() -> RuleResult:
            wire_thr = float(param("RULE-003", "wire", config.threshold_wire))
            intl_thr = float(param("RULE-003", "international", config.threshold_international))
            limit = wire_thr if tx.transaction_type == "wire" else intl_thr
            exceeded = tx.amount >= limit
            return RuleResult(
                rule_id="RULE-003",
                rule_type=RuleType.THRESHOLD,
                rule_name=f"Amount Threshold (>${limit:,.0f})",
                triggered=exceeded,
                detail=f"Amount ${tx.amount:,.2f} exceeds threshold ${limit:,.2f}" if exceeded else None,
                latency_ms=0.0,
            )

        def geography() -> RuleResult:
            countries = param("RULE-004", "countries", sorted(HIGH_RISK_COUNTRIES))
            country_set = set(countries) if isinstance(countries, (list, tuple, set)) else HIGH_RISK_COUNTRIES
            high_risk_geo = tx.destination_country in country_set if tx.destination_country else False
            return RuleResult(
                rule_id="RULE-004",
                rule_type=RuleType.GEOGRAPHY,
                rule_name="High-Risk Country Check",
                triggered=high_risk_geo,
                detail=f"Destination country {tx.destination_country} is high-risk" if high_risk_geo else None,
                latency_ms=0.0,
            )

        checks = {"RULE-001": sanctions, "RULE-002": pep, "RULE-003": threshold, "RULE-004": geography}

        def priority(rule_id: str) -> tuple[int, str]:
            cfg = rule_configs.get(rule_id) or {}
            return (int(cfg.get("priority", DEFAULT_RULE_PRIORITY)), rule_id)

        start = time.monotonic()
        results: list[RuleResult] = []
        for rule_id in sorted(checks, key=priority):
            cfg = rule_configs.get(rule_id) or {}
            if not cfg.get("enabled", True):
                continue
            r_start = time.monotonic()
            result = checks[rule_id]()
            result.latency_ms = round((time.monotonic() - r_start) * 1000, 2)
            results.append(result)
        return results, (time.monotonic() - start) * 1000

    def evaluate_rule(self, rule_def: dict, tx_data: dict, config: ScreeningConfig | None = None) -> dict:
        """Evaluate a single rule against transaction data (for simulation)."""
        config = config or ScreeningConfig.defaults()
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
            wire_thr = float(params.get("wire", config.threshold_wire))
            intl_thr = float(params.get("international", config.threshold_international))
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
    def _behavioral_score(
        self,
        tx: TransactionRequest,
        db: Session | None,
        user_id: str | None,
        config: ScreeningConfig,
    ) -> tuple[float, list[str] | None]:
        """Behavioral scoring via domain module (S2.1).

        Returns (anomaly_score, reasons[]).
        Falls back to heuristic scoring if db/user_id not provided.
        """
        account_id = tx.sender_id or tx.sender_name

        if db is not None and user_id is not None:
            result = score_behavioral(
                db=db,
                user_id=user_id,
                account_id=account_id,
                amount=tx.amount,
                transaction_type=tx.transaction_type.value,
                destination_country=tx.destination_country,
                receiver_name=tx.receiver_name,
                cold_start_threshold=config.behavioral_cold_start_threshold,
                warm_threshold=config.behavioral_warm_threshold,
            )
            return result.anomaly_score, result.reasons if result.reasons else None

        # Fallback: heuristic scoring without DB (for tests or when db not passed)
        score = 0.0
        reasons = []
        if tx.amount > 50000:
            score += 0.3
            reasons.append(f"High amount: {tx.amount}")
        elif tx.amount > 10000:
            score += 0.15
            reasons.append(f"Elevated amount: {tx.amount}")
        if tx.transaction_type.value == "international":
            score += 0.1
            reasons.append("International transaction type")
        if tx.destination_country in HIGH_RISK_COUNTRIES:
            score += 0.25
            reasons.append(f"High-risk country: {tx.destination_country}")
        return min(score, 1.0), reasons if reasons else None

    # --- Stage 5: ML Classification ---
    def _ml_classify(self, tx: TransactionRequest, behavioral: float) -> tuple[str, float]:
        """Simulate ML classification via RAG + LoRA (deterministic)."""
        if behavioral > 0.6:
            # High behavioral score → high_risk with confidence proportional to score
            confidence = min(0.7 + (behavioral - 0.6) * 0.75, 0.99)
            return "high_risk", confidence
        elif behavioral > 0.3:
            # Medium behavioral score → medium_risk with confidence proportional to distance from 0.3
            confidence = min(0.5 + (behavioral - 0.3) * 1.17, 0.85)
            return "medium_risk", confidence
        else:
            # Low behavioral score → low_risk with confidence inversely proportional to score
            confidence = min(0.6 + (0.3 - behavioral) * 1.17, 0.95)
            return "low_risk", confidence

    # --- Stage 6: Risk Scoring ---
    def _compute_risk(
        self,
        tx: TransactionRequest,
        rules: list[RuleResult],
        behavioral: float | None,
        ml_conf: float | None,
        weights: dict | None = None,
    ) -> float:
        weights = weights or ScreeningConfig.defaults().weights
        triggered_count = sum(1 for r in rules if r.triggered)
        rule_risk = min(triggered_count * 0.25, 1.0)

        score = rule_risk * weights["rules"]
        if behavioral is not None:
            score += behavioral * weights["behavioral"]
        else:
            score += 0.1  # baseline
        if ml_conf is not None:
            score += ml_conf * weights["model"]
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

    def _make_decision(
        self,
        risk: float,
        rules_triggered: bool,
        tx: TransactionRequest,
        rule_results: list[RuleResult] | None = None,
        bands: dict | None = None,
    ) -> ScreeningStatus:
        rule_results = rule_results or []
        bands = bands or ScreeningConfig.defaults().bands
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
        if risk >= bands["block"] or (rules_triggered and risk >= bands["block_if_rule"]):
            return ScreeningStatus.BLOCKED
        elif risk >= bands["flag"]:
            return ScreeningStatus.FLAGGED
        elif risk >= bands["review"]:
            return ScreeningStatus.IN_REVIEW
        return ScreeningStatus.APPROVED

    # --- Credit Tier Determination ---
    def _determine_tier(
        self,
        tx: TransactionRequest,
        rules_triggered: bool,
        rule_configs: dict[str, dict] | None = None,
        config: ScreeningConfig | None = None,
    ) -> CreditTier:
        rule_configs = rule_configs or {}
        config = config or ScreeningConfig.defaults()
        # Respect user's custom wire threshold when present
        try:
            wire_thr = float(((rule_configs.get("RULE-003") or {}).get("custom_parameters") or {}).get("wire", config.threshold_wire))
        except (TypeError, ValueError):
            wire_thr = config.threshold_wire
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
