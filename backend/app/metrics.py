"""Prometheus metrics (S4.4). Names follow the spec in FinShield-AI-Wiki.md §13.2 so the alert rules
in deploy/prometheus/alerts.yml match it. Labels are bounded (stage, outcome, rule, dependency):
the per-case SLA gauge in the spec would create one series per case, so cases_sla_approaching counts
cases inside the warning window instead.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

PIPELINE_LATENCY = Histogram("pipeline_latency_seconds", "Screening latency per pipeline stage", ["stage"],
                             buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
PIPELINE_TRANSACTIONS = Counter("pipeline_transactions_total", "Screened transactions by final outcome", ["outcome"])
PIPELINE_ERRORS = Counter("pipeline_errors_total", "Screening requests that failed with a server error")
PIPELINE_DEGRADED = Counter("pipeline_degraded_total", "Decisions taken with a dependency unavailable", ["dependency"])
PIPELINE_QUEUE_DEPTH = Gauge("pipeline_queue_depth", "Tasks waiting in the worker queue")
MODEL_LATENCY = Histogram("model_inference_latency_seconds", "Risk model scoring latency",
                          buckets=(0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10))
CLASSIFIER_CONFIDENCE = Histogram("classifier_confidence", "Risk model score distribution",
                                  buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0))
GATE_DISAGREEMENT = Counter("gate_disagreement_total",
                            "Model and final decision disagree (high_risk approved, or low_risk blocked by score)")
RULE_HITS = Counter("rule_hits_total", "Hard rule hits", ["rule"])
RAG_LATENCY = Histogram("rag_retrieval_latency_seconds", "RAG multi-hop retrieval latency",
                        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
CIRCUIT_BREAKER_STATE = Gauge("circuit_breaker_state", "0=closed 1=half-open 2=open", ["dependency"])
CASES_SLA_APPROACHING = Gauge("cases_sla_approaching", "Open cases within the SLA warning window")
LIST_AGE_HOURS = Gauge("sanctions_list_age_hours", "Hours since the last import of each list source", ["source"])

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route"])
UNHANDLED_ERRORS = Counter("unhandled_errors_total", "Unhandled exceptions (also sent to the error tracker)")
WEBHOOK_DELIVERIES = Counter("webhook_deliveries_total", "Webhook delivery attempts by result", ["result"])
JOB_RUNS = Counter("job_runs_total", "Background task executions by status", ["task", "status"])
AUDIT_CHAIN_BREAKS = Counter("audit_chain_breaks_total", "Audit chain verification failures")
RAG_STALE = Gauge("rag_corpus_stale", "1 when a RAG corpus is empty or embedded by another model")

BREAKER_VALUE = {"closed": 0, "half_open": 1, "open": 2}
