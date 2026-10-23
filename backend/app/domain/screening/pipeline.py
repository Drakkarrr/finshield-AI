"""Screening pipeline: a pure, deterministic function of (transaction, context).

No randomness, no clock in any decision, no I/O. Everything that needs the database or the network
(list snapshot, account history, RAG retrieval, model versions) is resolved by the API layer, through
circuit breakers, and handed in as a `ScreeningContext`. Same inputs -> same decision, score and
reasons (only latency_ms and the timestamp vary).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

from app.config_service import ScreeningConfig
from app.domain import behavioral
from app.domain.lists import WatchlistSnapshot
from app.domain.models_registry import ModelResult, RiskModel
from app.domain.screening import gating
from app.domain.screening.rules import country_set, run_rules, wire_threshold
from app.models import CreditTier, Reason, ScreeningResult, TransactionRequest

TYPE_RISK = {"crypto": 1.0, "international": 0.6, "wire": 0.4, "p2p": 0.3, "ach": 0.1, "card": 0.1}
BEHAVIORAL_TIER_AMOUNT = 5000.0
RULE_RISK_PER_HIT = 0.25
VELOCITY_SATURATION = 10  # transactions in 24h at which the velocity feature saturates
NEAR_MISS_FLOOR = 0.6  # name similarity below this carries no counterparty risk
RAG_USABLE = ("ok", "lexical_fallback")


@dataclass(frozen=True)
class ScreeningContext:
    config: ScreeningConfig
    model: RiskModel
    rule_configs: dict = field(default_factory=dict)
    watchlist: Optional[WatchlistSnapshot] = None
    high_risk_countries: frozenset[str] = frozenset()
    account_key: str = ""
    account_key_source: str = ""
    baseline: Optional[behavioral.Baseline] = None
    population: Optional[behavioral.Population] = None
    velocity_24h: int = 0
    rag_context: Optional[dict] = None
    rag_status: str = "disabled"  # ok | lexical_fallback | disabled | unavailable
    shadow_model: Optional[RiskModel] = None
    failed_dependencies: tuple[str, ...] = ()  # open breakers / failed calls seen by the API layer


@dataclass(frozen=True)
class ScreeningOutcome:
    result: ScreeningResult
    shadow: Optional[dict] = None


def _tier(tx: TransactionRequest, rules_triggered: bool, ctx: ScreeningContext) -> CreditTier:
    countries = country_set(ctx.rule_configs, ctx.high_risk_countries)
    if tx.amount >= wire_threshold(ctx.rule_configs, ctx.config) or (
            bool(tx.destination_country) and tx.destination_country in countries):
        return CreditTier.FULL_ML
    if rules_triggered or tx.amount >= BEHAVIORAL_TIER_AMOUNT:
        return CreditTier.BEHAVIORAL
    return CreditTier.RULE_ONLY


def model_features(tx: TransactionRequest, ctx: ScreeningContext) -> dict[str, float]:
    """The model's inputs, each normalised to [0, 1]. Independent of the rule and behavioral scores
    so the model is a separate signal in the blend, not a re-count of them."""
    countries = country_set(ctx.rule_configs, ctx.high_risk_countries)
    similarity = 0.0
    if ctx.watchlist is not None:
        similarity = max((ctx.watchlist.best_score(p, lt) for p in (tx.sender_name, tx.receiver_name) if p
                          for lt in ("sanctions", "pep")), default=0.0)
    rag_matches = (ctx.rag_context or {}).get("sanctions_matches") or []
    return {
        "amount_log": round(min(1.0, math.log10(tx.amount + 1) / 7), 4),
        "country_risk": 1.0 if tx.destination_country and tx.destination_country in countries else 0.0,
        "counterparty_risk": round(max(0.0, (similarity - NEAR_MISS_FLOOR) / (1 - NEAR_MISS_FLOOR)), 4),
        "rag_signal": round(max((float(m.get("similarity_score", 0)) for m in rag_matches), default=0.0), 4),
        "velocity": round(min(1.0, ctx.velocity_24h / VELOCITY_SATURATION), 4),
        "type_risk": TYPE_RISK.get(tx.transaction_type.value, 0.3),
    }


def screen(tx: TransactionRequest, ctx: ScreeningContext) -> ScreeningOutcome:
    cfg = ctx.config
    start = time.monotonic()
    stages = ["validation"]
    reasons: list[Reason] = []
    degraded = list(ctx.failed_dependencies)

    rule_results, _hits, rule_reasons, unavailable = run_rules(
        tx, ctx.rule_configs, cfg, ctx.watchlist, ctx.high_risk_countries)
    stages.append("rule_engine")
    reasons += rule_reasons
    degraded += [d for d in unavailable if d not in degraded]
    rules_triggered = any(r.triggered for r in rule_results)

    tier = _tier(tx, rules_triggered, ctx)
    credits = float(cfg.credit_cost[tier.value])

    beh: Optional[behavioral.BehavioralResult] = None
    if cfg.behavioral_enabled and tier in (CreditTier.BEHAVIORAL, CreditTier.FULL_ML):
        beh = behavioral.score(
            tx.amount, tx.destination_country, tx.receiver_name, ctx.baseline, ctx.population,
            behavioral.BehavioralConfig(trigger_warm=cfg.behavioral_trigger_warm,
                                        trigger_cold_start=cfg.behavioral_trigger_cold_start,
                                        cold_start_days=cfg.cold_start_days, min_history_txs=cfg.min_history_txs))
        stages.append("behavioral_analysis")
        reasons += beh.reasons

    rag_match = False
    rag_used = ctx.rag_status in RAG_USABLE and ctx.rag_context is not None
    if rag_used:
        assert ctx.rag_context is not None
        stages.append("rag_retrieval")
        lexical = ctx.rag_status == "lexical_fallback"
        for m in ctx.rag_context.get("sanctions_matches") or []:
            rag_match = True
            reasons.append(Reason(source="rag", feature="sanctions_similarity", value=m.get("matched_party"),
                                  contribution=0.0, entry_id=m.get("id"), name=m.get("name"),
                                  similarity=m.get("similarity_score"), degraded=lexical))
        for feature, key, label in (("policy_match", "policies", "title"), ("precedent_match", "similar_precedents",
                                                                              "decision")):
            top = (ctx.rag_context.get(key) or [None])[0]
            if top:
                reasons.append(Reason(source="rag", feature=feature, value=top.get(label), contribution=0.0,
                                      doc_id=top.get("id"), similarity=top.get("score"), degraded=lexical))
        if lexical:
            reasons.append(Reason(source="rag", feature="embedder", value="lexical_fallback", degraded=True,
                                  detail="semantic embedder unavailable; RAG evidence is lexical only"))
    else:
        reasons.append(Reason(source="rag", feature="retrieval", value=ctx.rag_status, degraded=True,
                              detail="RAG retrieval not used for this decision"))

    model_result: Optional[ModelResult] = None
    shadow: Optional[dict] = None
    if cfg.ml_enabled and tier == CreditTier.FULL_ML:
        features = model_features(tx, ctx)
        model_result = ctx.model.score(features)
        stages.append("ml_classification")
        reasons += model_result.reasons
        if ctx.shadow_model is not None:
            s = ctx.shadow_model.score(features)
            shadow = {"model_version": s.model_version, "label": s.label, "score": s.score,
                      "reasons": [r.model_dump() for r in s.reasons]}

    w = cfg.weights
    rule_risk = min(1.0, sum(1 for r in rule_results if r.triggered) * RULE_RISK_PER_HIT)
    parts = {"rules": rule_risk, "behavioral": beh.score if beh else 0.0,
             "model": model_result.score if model_result else 0.0}
    risk = round(min(1.0, sum(w[k] * v for k, v in parts.items())), 4)
    stages.append("risk_scoring")
    reasons += [Reason(source="score", feature=k, value=round(v, 4), contribution=round(w[k] * v, 4), weight=w[k])
                for k, v in parts.items()]

    status, gate_reasons = gating.decide(risk, rule_results, cfg.bands, bool(beh and beh.triggered), rag_match,
                                         degraded)
    stages.append("decision")
    reasons += gate_reasons
    if degraded:
        reasons.append(Reason(source="resilience", feature="degraded", value=degraded, degraded=True,
                              detail="a configured dependency was unavailable; decision held for human review"))

    result = ScreeningResult(
        transaction_id="",  # assigned when persisted
        idempotency_key=tx.idempotency_key,
        status=status,
        risk_score=risk,
        credit_tier=tier,
        credits_consumed=credits,
        rule_results=rule_results,
        behavioral_score=beh.score if beh else None,
        ml_classification=model_result.label if model_result else None,
        ml_confidence=model_result.score if model_result else None,
        total_latency_ms=round((time.monotonic() - start) * 1000, 2),
        pipeline_stages=stages,
        rag_context=ctx.rag_context if rag_used else None,
        reasons=reasons,
        model_version=model_result.model_version if model_result else ctx.model.version,
        degraded=bool(degraded),
        degraded_dependencies=degraded,
        rag_status=ctx.rag_status,
        account_key=ctx.account_key or None,
        account_key_source=ctx.account_key_source or None,
    )
    return ScreeningOutcome(result=result, shadow=shadow)
