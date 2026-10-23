"""FinShield AI — Observability: structured logging, tracing, and metrics (S4.4)."""
import logging
import os
import time
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST


# ============================================================
# STRUCTURED LOGGING (structlog)
# ============================================================

def setup_structured_logging():
    """Configure structlog for JSON structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


# Initialize structlog on module load
setup_structured_logging()

# Create structured logger
logger = structlog.get_logger("finshield")


# ============================================================
# PROMETHEUS METRICS
# ============================================================

# Transaction metrics
TRANSACTIONS_TOTAL = Counter(
    "finshield_transactions_total",
    "Total number of transactions processed",
    ["status", "credit_tier"]
)

TRANSACTION_DURATION = Histogram(
    "finshield_transaction_duration_seconds",
    "Time spent processing transactions",
    ["stage"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Risk scoring metrics
RISK_SCORES = Histogram(
    "finshield_risk_score",
    "Distribution of risk scores",
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

# Screening pipeline metrics
SCREENING_PIPELINE_DURATION = Histogram(
    "finshield_screening_pipeline_duration_seconds",
    "Time spent in each screening pipeline stage",
    ["stage"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# Active users gauge
ACTIVE_USERS = Gauge(
    "finshield_active_users",
    "Number of active users"
)

# Case metrics
CASES_TOTAL = Counter(
    "finshield_cases_total",
    "Total number of cases created",
    ["status", "severity"]
)

# Webhook metrics
WEBHOOKS_DELIVERED = Counter(
    "finshield_webhooks_delivered_total",
    "Total number of webhooks delivered",
    ["status"]
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    "finshield_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["breaker_name"]
)

# Cache metrics
CACHE_HITS = Counter(
    "finshield_cache_hits_total",
    "Total cache hits",
    ["cache_name"]
)

CACHE_MISSES = Counter(
    "finshield_cache_misses_total",
    "Total cache misses",
    ["cache_name"]
)


# ============================================================
# OPENTELEMETRY TRACING
# ============================================================

def setup_opentelemetry():
    """Configure OpenTelemetry for distributed tracing."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        
        # Only enable tracing if OTEL_ENABLED=true
        if os.getenv("OTEL_ENABLED", "false").lower() != "true":
            return None
        
        # Set up tracer provider
        provider = TracerProvider()
        
        # Export to console for development (in production, use OTLP exporter)
        if os.getenv("APP_ENV") == "development":
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer("finshield")
        
        logger.info("opentelemetry_initialized")
        return tracer
    
    except ImportError:
        logger.warning("opentelemetry_not_available")
        return None


# Initialize OpenTelemetry tracer
tracer = setup_opentelemetry()


# ============================================================
# TRACING DECORATORS
# ============================================================

def trace_pipeline_stage(stage_name: str):
    """Decorator to trace pipeline stages with OpenTelemetry."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if tracer is None:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(f"pipeline.{stage_name}") as span:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record metrics
                    SCREENING_PIPELINE_DURATION.labels(stage=stage_name).observe(duration)
                    
                    span.set_attribute("stage", stage_name)
                    span.set_attribute("duration_ms", duration * 1000)
                    
                    return result
                except Exception as e:
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


# ============================================================
# PROMETHEUS METRICS ENDPOINT
# ============================================================

def get_metrics() -> tuple[str, str]:
    """Generate Prometheus metrics in text format."""
    metrics = generate_latest()
    return metrics.decode("utf-8"), CONTENT_TYPE_LATEST


# ============================================================
# ALERT RULES (for external monitoring system)
# ============================================================

ALERT_RULES = {
    "high_error_rate": {
        "expr": "rate(finshield_transactions_total{status='error'}[5m]) / rate(finshield_transactions_total[5m]) > 0.05",
        "for": "5m",
        "labels": {"severity": "critical"},
        "annotations": {
            "summary": "High transaction error rate",
            "description": "More than 5% of transactions are failing"
        }
    },
    "slow_transactions": {
        "expr": "histogram_quantile(0.95, rate(finshield_transaction_duration_seconds_bucket[5m])) > 5",
        "for": "10m",
        "labels": {"severity": "warning"},
        "annotations": {
            "summary": "Slow transaction processing",
            "description": "95th percentile transaction time exceeds 5 seconds"
        }
    },
    "circuit_breaker_open": {
        "expr": "finshield_circuit_breaker_state == 1",
        "for": "2m",
        "labels": {"severity": "critical"},
        "annotations": {
            "summary": "Circuit breaker is open",
            "description": "A circuit breaker has tripped"
        }
    },
    "low_cache_hit_rate": {
        "expr": "rate(finshield_cache_hits_total[5m]) / (rate(finshield_cache_hits_total[5m]) + rate(finshield_cache_misses_total[5m])) < 0.5",
        "for": "15m",
        "labels": {"severity": "warning"},
        "annotations": {
            "summary": "Low cache hit rate",
            "description": "Cache hit rate is below 50%"
        }
    }
}
