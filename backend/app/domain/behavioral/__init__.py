"""Behavioral monitoring: per-account baselines and z-score anomaly scoring (S2.1).

Pure functions. Callers supply history and population statistics; nothing here touches the DB.
Cold-start policy (Wiki §4): an account younger than `cold_start_days` or with fewer than
`min_history_txs` transactions has no reliable baseline of its own, so it is scored against the
population of the owner's accounts, with the stricter cold-start trigger threshold, and every
reason is marked cold_start so reviewers know the signal is weaker.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from app.models import Reason

Z_SATURATION = 3.0  # z-score at which the amount anomaly saturates to 1.0
NOVEL_COUNTRY_BUMP = 0.2
NOVEL_PAYEE_BUMP = 0.15
TYPICAL_SHARE = 0.1  # a value seen in >= 10% of history is "typical"


@dataclass(frozen=True)
class HistoryRow:
    amount: float
    created_at: datetime
    destination_country: Optional[str] = None
    receiver_name: Optional[str] = None
    transaction_type: Optional[str] = None


@dataclass(frozen=True)
class Baseline:
    total_transactions: int
    avg_amount: float
    std_dev_amount: float
    min_amount: float
    max_amount: float
    first_transaction_at: datetime
    last_transaction_at: datetime
    history_days: int
    typical_countries: list[str] = field(default_factory=list)
    typical_payees: list[str] = field(default_factory=list)
    typical_tx_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Population:
    count: int
    avg_amount: float
    std_dev_amount: float


@dataclass(frozen=True)
class BehavioralConfig:
    trigger_warm: float
    trigger_cold_start: float
    cold_start_days: int
    min_history_txs: int


@dataclass(frozen=True)
class BehavioralResult:
    score: float
    triggered: bool
    cold_start: bool
    threshold: float
    z_score: Optional[float]
    reasons: list[Reason]


def _mean_std(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    return mean, math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))


def _typical(values: Iterable[Optional[str]], total: int) -> list[str]:
    counts: dict[str, int] = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    return sorted(v for v, c in counts.items() if c >= total * TYPICAL_SHARE)


def compute_baseline(history: list[HistoryRow]) -> Optional[Baseline]:
    """Baseline from an account's prior transactions (any order). None when there is no history."""
    if not history:
        return None
    rows = sorted(history, key=lambda r: r.created_at)
    amounts = [r.amount for r in rows]
    mean, std = _mean_std(amounts)
    return Baseline(
        total_transactions=len(rows),
        avg_amount=mean,
        std_dev_amount=std,
        min_amount=min(amounts),
        max_amount=max(amounts),
        first_transaction_at=rows[0].created_at,
        last_transaction_at=rows[-1].created_at,
        history_days=(rows[-1].created_at - rows[0].created_at).days,
        typical_countries=_typical((r.destination_country for r in rows), len(rows)),
        typical_payees=_typical((r.receiver_name for r in rows), len(rows)),
        typical_tx_types=_typical((r.transaction_type for r in rows), len(rows)),
    )


def compute_population(amounts: list[float]) -> Optional[Population]:
    if not amounts:
        return None
    mean, std = _mean_std(amounts)
    return Population(count=len(amounts), avg_amount=mean, std_dev_amount=std)


def is_cold_start(baseline: Optional[Baseline], cfg: BehavioralConfig) -> bool:
    return (baseline is None or baseline.history_days < cfg.cold_start_days
            or baseline.total_transactions < cfg.min_history_txs)


def _z(amount: float, mean: float, std: float) -> float:
    if std > 0:
        return abs(amount - mean) / std
    return 0.0 if amount == mean else Z_SATURATION


def score(
    amount: float,
    destination_country: Optional[str],
    receiver_name: Optional[str],
    baseline: Optional[Baseline],
    population: Optional[Population],
    cfg: BehavioralConfig,
) -> BehavioralResult:
    cold = is_cold_start(baseline, cfg)
    threshold = cfg.trigger_cold_start if cold else cfg.trigger_warm
    reasons: list[Reason] = []

    if not cold:
        assert baseline is not None
        z = _z(amount, baseline.avg_amount, baseline.std_dev_amount)
        amount_part = min(1.0, z / Z_SATURATION)
        reasons.append(Reason(source="behavioral", feature="amount_z_score", value=round(z, 4),
                              contribution=round(amount_part, 4), cold_start=False,
                              basis="account", baseline_mean=round(baseline.avg_amount, 2),
                              baseline_std=round(baseline.std_dev_amount, 2)))
        total = amount_part
        if destination_country and baseline.typical_countries and destination_country not in baseline.typical_countries:
            total += NOVEL_COUNTRY_BUMP
            reasons.append(Reason(source="behavioral", feature="novel_destination_country", value=destination_country,
                                  contribution=NOVEL_COUNTRY_BUMP, cold_start=False))
        if receiver_name and baseline.typical_payees and receiver_name not in baseline.typical_payees:
            total += NOVEL_PAYEE_BUMP
            reasons.append(Reason(source="behavioral", feature="novel_payee", value=receiver_name,
                                  contribution=NOVEL_PAYEE_BUMP, cold_start=False))
    elif population is not None and population.count >= cfg.min_history_txs:
        z = _z(amount, population.avg_amount, population.std_dev_amount)
        total = min(1.0, z / Z_SATURATION)
        reasons.append(Reason(source="behavioral", feature="amount_z_score", value=round(z, 4),
                              contribution=round(total, 4), cold_start=True, basis="population",
                              baseline_mean=round(population.avg_amount, 2),
                              baseline_std=round(population.std_dev_amount, 2),
                              detail="account history below the cold-start window; scored against the population"))
    else:
        z = None
        total = 0.0
        reasons.append(Reason(source="behavioral", feature="insufficient_history", value=None, contribution=0.0,
                              cold_start=True, detail="no reliable account or population baseline yet"))

    total = round(min(1.0, total), 4)
    triggered = total >= threshold
    reasons.append(Reason(source="behavioral", feature="trigger", value=total, contribution=0.0,
                          threshold=threshold, triggered=triggered, cold_start=cold))
    return BehavioralResult(score=total, triggered=triggered, cold_start=cold, threshold=threshold,
                            z_score=round(z, 4) if z is not None else None, reasons=reasons)
