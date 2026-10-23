"""Circuit breaker decorator for wrapping external service calls."""

from datetime import datetime
from functools import wraps
from typing import Callable, Any

from sqlalchemy.orm import Session

from app.db_models import CircuitBreaker


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and call should be skipped."""
    pass


class CircuitBreakerDecorator:
    """Decorator that wraps calls with circuit breaker logic."""

    def __init__(self, dependency: str, db: Session):
        self.dependency = dependency
        self.db = db

    def _get_breaker(self) -> CircuitBreaker:
        """Get or create circuit breaker for this dependency."""
        breaker = self.db.query(CircuitBreaker).filter(
            CircuitBreaker.dependency == self.dependency
        ).first()
        if not breaker:
            breaker = CircuitBreaker(dependency=self.dependency)
            self.db.add(breaker)
            self.db.commit()
            self.db.refresh(breaker)
        return breaker

    def _check_half_open(self, breaker: CircuitBreaker) -> None:
        """Check if open breaker should transition to half-open."""
        if breaker.state != "open":
            return

        if breaker.last_state_change_at:
            elapsed = (datetime.utcnow() - breaker.last_state_change_at).total_seconds()
            if elapsed >= breaker.cooldown_seconds:
                breaker.state = "half_open"
                breaker.success_count = 0
                breaker.last_state_change_at = datetime.utcnow()
                self.db.commit()

    def _record_success(self, breaker: CircuitBreaker) -> None:
        """Record a successful call."""
        now = datetime.utcnow()
        breaker.success_count += 1

        if breaker.state == "half_open":
            if breaker.success_count >= breaker.half_open_max_calls:
                breaker.state = "closed"
                breaker.failure_count = 0
                breaker.success_count = 0
                breaker.last_state_change_at = now
        elif breaker.state == "closed":
            breaker.failure_count = max(0, breaker.failure_count - 1)

        self.db.commit()

    def _record_failure(self, breaker: CircuitBreaker) -> None:
        """Record a failed call."""
        now = datetime.utcnow()
        breaker.failure_count += 1
        breaker.last_failure_at = now

        if breaker.state == "closed" and breaker.failure_count >= breaker.failure_threshold:
            breaker.state = "open"
            breaker.last_state_change_at = now
        elif breaker.state == "half_open":
            breaker.state = "open"
            breaker.last_state_change_at = now
            breaker.failure_count = 1

        self.db.commit()

    def __call__(self, func: Callable) -> Callable:
        """Decorator that wraps function with circuit breaker logic."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = self._get_breaker()
            self._check_half_open(breaker)

            # If circuit is open, raise exception to trigger degraded mode
            if breaker.state == "open":
                raise CircuitBreakerOpen(
                    f"Circuit breaker for {self.dependency} is open"
                )

            # Try the call
            try:
                result = func(*args, **kwargs)
                self._record_success(breaker)
                return result
            except Exception as e:
                self._record_failure(breaker)
                raise

        return wrapper


def with_circuit_breaker(dependency: str, db: Session):
    """Decorator factory for circuit breaker wrapping."""
    decorator = CircuitBreakerDecorator(dependency, db)
    return decorator


def get_degraded_action(dependency: str) -> str:
    """Get the degraded action for a dependency when circuit is open.

    Returns the action to take when a dependency is unavailable.
    All degraded actions route to human review, never auto-approve.
    """
    degraded_actions = {
        "model_server": "route_to_human_review",
        "pgvector": "skip_rag_enrichment",
        "redis": "skip_caching",
        "notification_service": "queue_for_retry",
    }
    return degraded_actions.get(dependency, "route_to_human_review")
