"""Hard rules (RULE-001..004): definitions for the admin UI, evaluation, and simulation."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from app.config_service import ScreeningConfig
from app.domain.lists import ListHit, WatchlistSnapshot
from app.models import Reason, RuleResult, RuleType, TransactionRequest

DEFAULT_RULE_PRIORITY = 100  # lower runs first; ties break on rule_id

RULE_META = {
    "RULE-001": ("sanctions", "OFAC Sanctions List Match", "block",
                 "Blocks transactions where the sender or receiver matches a sanctions list entry."),
    "RULE-002": ("pep", "Politically Exposed Person Check", "flag",
                 "Flags transactions involving politically exposed persons for enhanced due diligence."),
    "RULE-003": ("threshold", "Amount Threshold", "review",
                 "Reviews transactions that exceed reporting thresholds for their type."),
    "RULE-004": ("geography", "High-Risk Country Check", "escalate",
                 "Blocks transactions destined for embargoed or high-risk jurisdictions."),
}

LIST_RULES = {"RULE-001": "sanctions", "RULE-002": "pep"}


def rule_definitions(config: ScreeningConfig, high_risk_countries: frozenset[str],
                     watchlist: Optional[WatchlistSnapshot]) -> list[dict]:
    """The hard-rule definitions for the Rules UI. `parameters` are user-editable; `metadata` is not."""
    out = []
    for rule_id, (rtype, name, action, description) in RULE_META.items():
        params: dict[str, Any] = {}
        meta: dict[str, Any] = {"editable": rule_id in ("RULE-003", "RULE-004")}
        if rule_id in LIST_RULES:
            lt = LIST_RULES[rule_id]
            meta["list_size"] = sum(1 for e in watchlist.entries if e.list_type == lt) if watchlist else 0
            meta["list_versions"] = ({s: v for s, v in watchlist.versions.items()
                                      if any(e.source == s and e.list_type == lt for e in watchlist.entries)}
                                     if watchlist else {})
            meta["fuzzy_threshold"] = config.list_fuzzy_threshold
        elif rule_id == "RULE-003":
            params = {"wire": config.threshold_wire, "international": config.threshold_international}
        else:
            params = {"countries": sorted(high_risk_countries)}
        out.append({"rule_id": rule_id, "rule_type": rtype, "name": name, "description": description,
                    "enabled": True, "action": action, "parameters": params, "metadata": meta})
    return out


def _param(rule_configs: dict, rule_id: str, key: str, default: Any) -> Any:
    cfg = rule_configs.get(rule_id) or {}
    return (cfg.get("custom_parameters") or {}).get(key, default)


def country_set(rule_configs: dict, high_risk_countries: frozenset[str]) -> frozenset[str]:
    countries = _param(rule_configs, "RULE-004", "countries", None)
    if isinstance(countries, (list, tuple, set)):
        return frozenset(str(c) for c in countries)
    return high_risk_countries


def wire_threshold(rule_configs: dict, config: ScreeningConfig) -> float:
    try:
        return float(_param(rule_configs, "RULE-003", "wire", config.threshold_wire))
    except (TypeError, ValueError):
        return config.threshold_wire


def run_rules(
    tx: TransactionRequest,
    rule_configs: dict,
    config: ScreeningConfig,
    watchlist: Optional[WatchlistSnapshot],
    high_risk_countries: frozenset[str],
) -> tuple[list[RuleResult], list[ListHit], list[Reason], list[str]]:
    """Returns (rule results in priority order, list hits, reasons, unavailable dependencies)."""
    hits: list[ListHit] = []
    reasons: list[Reason] = []
    unavailable: list[str] = []
    parties = [p for p in (tx.sender_name, tx.receiver_name) if p]

    def list_rule(rule_id: str) -> RuleResult:
        list_type = LIST_RULES[rule_id]
        rtype, name, _action, _ = RULE_META[rule_id]
        if watchlist is None or not watchlist.has(list_type):
            unavailable.append(f"{list_type}_list")
            reasons.append(Reason(source="list", feature=f"{list_type}_list_unavailable", value=None,
                                  detail=f"no {list_type} list data loaded; {rule_id} could not be evaluated"))
            return RuleResult(rule_id=rule_id, rule_type=RuleType(rtype), rule_name=name, triggered=False,
                              detail=f"{list_type} list unavailable", latency_ms=0.0)
        rule_hits = [h for party in parties for h in watchlist.match(party, list_type, config.list_fuzzy_threshold)]
        hits.extend(rule_hits)
        for h in rule_hits:
            provenance = h.as_dict()
            provenance["list_source"] = provenance.pop("source")
            reasons.append(Reason(source="list", feature=f"{list_type}_match", value=h.query, contribution=0.0,
                                  detail=f"{h.match_type} match ({h.score:.2f}) on '{h.matched_name}'",
                                  rule_id=rule_id, **provenance))
        detail = None
        if rule_hits:
            top = rule_hits[0]
            detail = (f"'{top.query}' matched {top.source} entry {top.entry_id} ('{top.primary_name}', "
                      f"list {top.list_version}, {top.match_type} {top.score:.2f})")
        return RuleResult(rule_id=rule_id, rule_type=RuleType(rtype), rule_name=name, triggered=bool(rule_hits),
                          detail=detail, latency_ms=0.0)

    def threshold() -> RuleResult:
        wire_thr = wire_threshold(rule_configs, config)
        intl_thr = float(_param(rule_configs, "RULE-003", "international", config.threshold_international))
        limit = wire_thr if tx.transaction_type == "wire" else intl_thr
        exceeded = tx.amount >= limit
        if exceeded:
            reasons.append(Reason(source="rule", feature="amount_threshold", value=tx.amount, rule_id="RULE-003",
                                  threshold=limit, detail=f"amount {tx.amount:,.2f} >= {limit:,.2f}"))
        return RuleResult(rule_id="RULE-003", rule_type=RuleType.THRESHOLD, rule_name=f"Amount Threshold (>${limit:,.0f})",
                          triggered=exceeded,
                          detail=f"Amount ${tx.amount:,.2f} exceeds threshold ${limit:,.2f}" if exceeded else None,
                          latency_ms=0.0)

    def geography() -> RuleResult:
        countries = country_set(rule_configs, high_risk_countries)
        high_risk = bool(tx.destination_country) and tx.destination_country in countries
        if high_risk:
            reasons.append(Reason(source="rule", feature="high_risk_country", value=tx.destination_country,
                                  rule_id="RULE-004"))
        return RuleResult(rule_id="RULE-004", rule_type=RuleType.GEOGRAPHY, rule_name="High-Risk Country Check",
                          triggered=high_risk,
                          detail=f"Destination country {tx.destination_country} is high-risk" if high_risk else None,
                          latency_ms=0.0)

    checks: dict[str, Callable[[], RuleResult]] = {
        "RULE-001": lambda: list_rule("RULE-001"), "RULE-002": lambda: list_rule("RULE-002"),
        "RULE-003": threshold, "RULE-004": geography,
    }

    def priority(rule_id: str) -> tuple[int, str]:
        return (int((rule_configs.get(rule_id) or {}).get("priority", DEFAULT_RULE_PRIORITY)), rule_id)

    results: list[RuleResult] = []
    for rule_id in sorted(checks, key=priority):
        if not (rule_configs.get(rule_id) or {}).get("enabled", True):
            continue
        start = time.monotonic()
        result = checks[rule_id]()
        result.latency_ms = round((time.monotonic() - start) * 1000, 2)
        results.append(result)
    return results, hits, reasons, unavailable


def evaluate_rule(rule_def: dict, tx_data: dict, config: ScreeningConfig,
                  watchlist: Optional[WatchlistSnapshot], high_risk_countries: frozenset[str]) -> dict:
    """Evaluate one rule against a historical transaction (for simulation)."""
    rule_id = rule_def["rule_id"]
    if rule_id in LIST_RULES:
        list_type = LIST_RULES[rule_id]
        if watchlist is None or not watchlist.has(list_type):
            return {"triggered": False, "unavailable": True}
        parties = [tx_data.get("sender_name") or "", tx_data.get("receiver_name") or ""]
        return {"triggered": any(watchlist.match(p, list_type, config.list_fuzzy_threshold) for p in parties if p)}
    params = rule_def.get("parameters", {})
    if rule_id == "RULE-003":
        limit = float(params.get("wire", config.threshold_wire)) if tx_data.get("transaction_type") == "wire" \
            else float(params.get("international", config.threshold_international))
        return {"triggered": tx_data.get("amount", 0) >= limit}
    if rule_id == "RULE-004":
        countries = params.get("countries")
        cs = set(countries) if isinstance(countries, (list, tuple, set)) else high_risk_countries
        dest = tx_data.get("destination_country")
        return {"triggered": bool(dest) and dest in cs}
    return {"triggered": False}
