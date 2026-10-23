"""Evaluation harness (S2.7): per-stage precision/recall/F1/FPR, confusion matrix, retrieval quality.

  cd backend && APP_ENV=test python -m tests.eval.run_eval                  # compare to baseline
  ... python -m tests.eval.run_eval --write-baseline                        # record a new baseline
  ... python -m tests.eval.run_eval --override rules.threshold.wire=1e9     # prove a regression fails

Runs the pure screening pipeline on labelled scenarios (no DB, no network) with the fictional list
fixture, and scores retrieval over the shipped seed corpus with the configured embedder
(RAG_EMBEDDER, default hash here; the backend image has MiniLM). Exits 1 if any metric falls more
than TOLERANCE below tests/eval/baseline.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")

import numpy as np  # noqa: E402

from app.config_service import ScreeningConfig  # noqa: E402
from app.domain import behavioral  # noqa: E402
from app.domain.lists import WatchlistSnapshot  # noqa: E402
from app.domain.lists.importers import parse_ofac_sdn, parse_pep_csv  # noqa: E402
from app.domain.models_registry.registry import BUILTIN  # noqa: E402
from app.domain.screening import ScreeningContext, screen  # noqa: E402
from app.models import TransactionRequest  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "fixtures" / "lists"
BASELINE = HERE / "baseline.json"
REPORT = HERE / "report.json"
TOLERANCE = 0.01
COUNTRIES = frozenset({"KP", "IR", "SY", "CU", "RU"})
DECISION = {"approved": "approve", "in_review": "review", "flagged": "flag", "blocked": "block"}
CLASSES = ("approve", "review", "flag", "block")
EPOCH = datetime(2026, 1, 1)


def watchlists() -> dict[str, WatchlistSnapshot | None]:
    read = lambda n: (FIXTURES / n).read_text(encoding="utf-8")  # noqa: E731
    sdn, v1 = parse_ofac_sdn(read("sdn.csv"), read("alt.csv"), read("add.csv"), source="FIXTURE-OFAC")
    pep, v2 = parse_pep_csv(read("pep.csv"), source="FIXTURE-PEP")
    return {"all": WatchlistSnapshot(sdn + pep, {"FIXTURE-OFAC": v1, "FIXTURE-PEP": v2}),
            "sanctions_only": WatchlistSnapshot(sdn, {"FIXTURE-OFAC": v1}), "none": None}


def history(spec: dict) -> list[behavioral.HistoryRow]:
    n, days = spec["n"], spec["days"]
    step = timedelta(days=days / max(n - 1, 1))
    pattern = (-1.0, 0.0, 1.0, 0.5, -0.5)
    return [behavioral.HistoryRow(amount=spec["mean"] + spec["spread"] * pattern[i % 5], created_at=EPOCH + i * step,
                                  destination_country=spec.get("country"), receiver_name=spec.get("payee", "Landlord"),
                                  transaction_type="ach") for i in range(n)]


def run_scenarios(config: ScreeningConfig) -> list[dict]:
    lists = watchlists()
    data = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    out = []
    for sc in data["scenarios"]:
        tx = TransactionRequest(currency="USD", idempotency_key=sc["id"], **sc["tx"])
        pop = sc.get("population")
        ctx = ScreeningContext(
            config=config, model=BUILTIN, watchlist=lists[sc.get("lists", "all")], high_risk_countries=COUNTRIES,
            account_key=tx.account_id or tx.sender_name, account_key_source="account_id",
            baseline=behavioral.compute_baseline(history(sc["baseline"])) if sc.get("baseline") else None,
            population=behavioral.Population(pop["count"], pop["mean"], pop["std"]) if pop else None,
            velocity_24h=sc.get("velocity_24h", 0),
            rag_context={"policies": [], "similar_precedents": [], **sc["rag"]} if "rag" in sc else None,
            rag_status="ok" if "rag" in sc else "disabled",
        )
        r = screen(tx, ctx).result
        out.append({
            "id": sc["id"], "category": sc["category"], "expected": sc["expected"]["decision"],
            "actual": DECISION[r.status.value], "labels": sc.get("labels", {}),
            "fired": {
                "rules": any(x.triggered for x in r.rule_results),
                "behavioral": any(x.source == "behavioral" and x.feature == "trigger" and getattr(x, "triggered", False)
                                  for x in r.reasons),
                "rag": any(x.source == "rag" and x.feature == "sanctions_similarity" for x in r.reasons),
                "model": r.ml_classification in ("medium_risk", "high_risk"),
            },
        })
    return out


def binary(pairs: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for e, a in pairs if e and a)
    fp = sum(1 for e, a in pairs if not e and a)
    fn = sum(1 for e, a in pairs if e and not a)
    tn = sum(1 for e, a in pairs if not e and not a)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "fpr": round(fpr, 4),
            "support": tp + fn, "n": len(pairs)}


def metrics(results: list[dict]) -> dict:
    stages = {stage: binary([(r["labels"][stage], r["fired"][stage]) for r in results if stage in r["labels"]])
              for stage in ("rules", "behavioral", "rag", "model")}
    stages["final_gate"] = binary([(r["expected"] != "approve", r["actual"] != "approve") for r in results])
    confusion = {e: {a: sum(1 for r in results if r["expected"] == e and r["actual"] == a) for a in CLASSES}
                 for e in CLASSES}
    exact = sum(1 for r in results if r["expected"] == r["actual"]) / len(results)
    return {"stages": stages, "confusion": confusion, "decision_accuracy": round(exact, 4),
            "misses": [{"id": r["id"], "expected": r["expected"], "actual": r["actual"]}
                       for r in results if r["expected"] != r["actual"]]}


def retrieval() -> dict:
    from app.domain.rag import seed as seed_module
    from app.domain.rag.embedders import load_embedder

    os.environ.setdefault("RAG_EMBEDDER", "hash")
    embedder = load_embedder()
    docs: list[dict] = []

    class Capture:  # collect the shipped seed corpus without a database
        def counts(self):
            return {"compliance_documents": 0, "sanctions_entries": 0, "precedent_decisions": 0}

        def add_compliance_document(self, **kw):
            docs.append(kw)

        def add_sanctions_entry(self, **kw):
            pass

        def add_precedent_decision(self, **kw):
            pass

    seed_module.seed_rag_data(Capture())  # type: ignore[arg-type]
    ids = [d["doc_id"] for d in docs]
    matrix = np.asarray(embedder.embed([f"{d['title']} {d['content']}" for d in docs]), dtype=np.float32)
    queries = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))["retrieval"]
    out = {}
    for subset, qs in (("lexical", [q for q in queries if not q.get("paraphrase")]),
                       ("paraphrase", [q for q in queries if q.get("paraphrase")])):
        ranks = []
        for q in qs:
            v = np.asarray(embedder.embed([q["query"]])[0], dtype=np.float32)
            order = [ids[i] for i in np.argsort(-(matrix @ v), kind="stable")]
            ranks.append(order.index(q["expected"]) + 1)
        out[subset] = {"hit@1": round(sum(r == 1 for r in ranks) / len(ranks), 4),
                       "hit@3": round(sum(r <= 3 for r in ranks) / len(ranks), 4),
                       "mrr": round(sum(1 / r for r in ranks) / len(ranks), 4), "n": len(ranks)}
    return {"embedder": embedder.name, "semantic": embedder.semantic, **out}


def flatten(report: dict) -> dict[str, float]:
    flat = {f"{stage}.{k}": v for stage, m in report["stages"].items() for k, v in m.items()
            if k in ("precision", "recall", "f1")}
    flat["decision_accuracy"] = report["decision_accuracy"]
    rag = report["retrieval"]
    for subset in ("lexical", "paraphrase"):
        for k in ("hit@1", "mrr"):
            flat[f"retrieval[{rag['embedder']}].{subset}.{k}"] = rag[subset][k]
    return flat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--override", action="append", default=[], metavar="FIELD=VALUE",
                    help="ScreeningConfig field override, e.g. threshold_wire=1e9 or rules.threshold.wire=1e9")
    args = ap.parse_args(argv)

    config = ScreeningConfig.defaults()
    for item in args.override:
        key, value = item.split("=", 1)
        field = {"rules.threshold.wire": "threshold_wire", "rules.threshold.international": "threshold_international",
                 "lists.fuzzy_threshold": "list_fuzzy_threshold"}.get(key, key)
        config = dataclasses.replace(config, **{field: type(getattr(config, field))(float(value))})

    report = metrics(run_scenarios(config))
    report["retrieval"] = retrieval()
    report["generated_at"] = datetime.utcnow().isoformat()
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{'stage':12} {'precision':>9} {'recall':>7} {'f1':>6} {'fpr':>6} {'support':>8}")
    for stage, m in report["stages"].items():
        print(f"{stage:12} {m['precision']:9.3f} {m['recall']:7.3f} {m['f1']:6.3f} {m['fpr']:6.3f} {m['support']:8}")
    print(f"\ndecision accuracy {report['decision_accuracy']:.3f}   confusion (rows=expected, cols=actual "
          f"{'/'.join(CLASSES)}):")
    for e in CLASSES:
        print(f"  {e:8} " + " ".join(f"{report['confusion'][e][a]:3}" for a in CLASSES))
    rag = report["retrieval"]
    print(f"\nretrieval ({rag['embedder']}, semantic={rag['semantic']}): " + "; ".join(
        f"{s} hit@1={rag[s]['hit@1']:.2f} mrr={rag[s]['mrr']:.2f}" for s in ("lexical", "paraphrase")))
    if report["misses"]:
        print("misses:", ", ".join(f"{m['id']} ({m['expected']}->{m['actual']})" for m in report["misses"]))

    flat = flatten(report)
    if args.write_baseline:
        existing = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
        existing.update(flat)
        BASELINE.write_text(json.dumps(dict(sorted(existing.items())), indent=2) + "\n", encoding="utf-8")
        print(f"\nbaseline written: {BASELINE}")
        return 0
    if not BASELINE.exists():
        print("\nno baseline committed; run with --write-baseline")
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    regressions = [f"{k}: {flat[k]:.4f} < baseline {v:.4f}" for k, v in baseline.items()
                   if k in flat and flat[k] < v - TOLERANCE]
    if regressions:
        print("\nREGRESSION:\n  " + "\n  ".join(regressions))
        return 1
    print(f"\nno regression against {BASELINE.name} ({sum(k in flat for k in baseline)} metrics checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
