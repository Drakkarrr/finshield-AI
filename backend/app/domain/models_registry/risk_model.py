"""RiskModel protocol and the v1 hand-weighted logistic scorer.

v1 is NOT trained: there is no labelled dataset, so its weights are expert-defined and stored with
the model version (model_versions.params). Each feature's logit contribution is returned as a
reason. Anything implementing `RiskModel` (e.g. a trained sklearn pipeline wrapped to accept the
same feature dict) can replace it without touching callers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.models import Reason

# Every feature is pre-normalised to [0, 1] by the screening pipeline.
FEATURES = ("amount_log", "country_risk", "counterparty_risk", "rag_signal", "velocity", "type_risk")

V1_PARAMS: dict = {
    "bias": -3.0,
    "weights": {
        "amount_log": 2.5,
        "country_risk": 2.0,
        "counterparty_risk": 2.5,
        "rag_signal": 1.5,
        "velocity": 1.5,
        "type_risk": 1.0,
    },
    "labels": {"high_risk": 0.7, "medium_risk": 0.4},
}


@dataclass(frozen=True)
class ModelResult:
    label: str
    score: float  # probability-like risk in [0, 1]
    reasons: list[Reason]
    model_version: str


class RiskModel(Protocol):
    version: str

    def score(self, features: dict[str, float]) -> ModelResult: ...


class WeightedLogisticModel:
    """score = sigmoid(bias + sum(w_i * x_i)); deterministic for a given (params, features)."""

    def __init__(self, version: str, params: dict):
        self.version = version
        self.bias = float(params["bias"])
        self.weights = {k: float(v) for k, v in params["weights"].items()}
        self.labels = params["labels"]
        missing = set(FEATURES) - set(self.weights)
        if missing:
            raise ValueError(f"model {version} has no weight for features {sorted(missing)}")

    def score(self, features: dict[str, float]) -> ModelResult:
        logit = self.bias
        reasons: list[Reason] = []
        for name in FEATURES:
            x = float(features.get(name, 0.0))
            part = self.weights[name] * x
            logit += part
            reasons.append(Reason(source="model", feature=name, value=round(x, 4), contribution=round(part, 4),
                                  weight=self.weights[name], model_version=self.version))
        p = 1.0 / (1.0 + math.exp(-logit))
        if p >= self.labels["high_risk"]:
            label = "high_risk"
        elif p >= self.labels["medium_risk"]:
            label = "medium_risk"
        else:
            label = "low_risk"
        return ModelResult(label=label, score=round(p, 4), reasons=reasons, model_version=self.version)
