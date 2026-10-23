"""Circuit breakers around real dependencies (S2.6).

closed --(failure_threshold consecutive failures)--> open --(cooldown elapsed)--> half_open
half_open --(half_open_max_calls successes)--> closed;  half_open --(any failure)--> open.

State is held in-process (a breaker protects *this* instance's calls, as is standard) and the hot
path takes no extra DB connection: a request already holds one, and a second per dependency call
exhausts the pool under load. The `circuit_breakers` table is the persisted view: each breaker's
configuration and last state are loaded from it on first use, and every state transition is
written back, so the dashboard and /api/health/ready see real state.

Callers must treat DependencyUnavailable as a degraded dependency: the decision gate then refuses
to auto-approve.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, TypeVar

from app.database import SessionLocal
from app.db_models import CircuitBreaker

logger = logging.getLogger("finshield.resilience")
T = TypeVar("T")

DEPENDENCIES = ("watchlist", "rag", "risk_model", "webhook_delivery")
DEFAULTS = {"failure_threshold": 3, "cooldown_seconds": 30, "half_open_max_calls": 1}


class DependencyUnavailable(Exception):
    def __init__(self, dependency: str, reason: str):
        super().__init__(f"{dependency} unavailable: {reason}")
        self.dependency = dependency
        self.reason = reason


@dataclass
class _State:
    state: str
    failures: int
    successes: int
    changed_at: datetime
    last_failure_at: Optional[datetime]
    failure_threshold: int
    cooldown_seconds: int
    half_open_max_calls: int


_lock = threading.Lock()
_states: dict[str, _State] = {}


def _load(dependency: str) -> _State:
    db = SessionLocal()
    try:
        row = db.query(CircuitBreaker).filter(CircuitBreaker.dependency == dependency).first()
        if row is None:
            row = CircuitBreaker(dependency=dependency, state="closed", failure_count=0, success_count=0,
                                 last_state_change_at=datetime.utcnow(), **DEFAULTS)
            db.add(row)
            db.commit()
        return _State(state=row.state or "closed", failures=row.failure_count or 0, successes=row.success_count or 0,
                      changed_at=row.last_state_change_at or datetime.utcnow(), last_failure_at=row.last_failure_at,
                      failure_threshold=row.failure_threshold or DEFAULTS["failure_threshold"],
                      cooldown_seconds=row.cooldown_seconds if row.cooldown_seconds is not None
                      else DEFAULTS["cooldown_seconds"],
                      half_open_max_calls=row.half_open_max_calls or DEFAULTS["half_open_max_calls"])
    finally:
        db.close()


def _get(dependency: str) -> _State:
    with _lock:
        st = _states.get(dependency)
    if st is None:
        st = _load(dependency)
        with _lock:
            st = _states.setdefault(dependency, st)
    return st


def _persist(dependency: str, st: _State) -> None:
    db = SessionLocal()
    try:
        row = db.query(CircuitBreaker).filter(CircuitBreaker.dependency == dependency).first()
        if row is not None:
            row.state = st.state
            row.failure_count = st.failures
            row.success_count = st.successes
            row.last_state_change_at = st.changed_at
            row.last_failure_at = st.last_failure_at
            db.commit()
    except Exception:  # visibility only: never let persisting a breaker break the call it guards
        logger.exception("could not persist circuit breaker %s", dependency)
    finally:
        db.close()


def _transition(dependency: str, st: _State, state: str, now: datetime) -> None:
    logger.warning("circuit breaker %s: %s -> %s", dependency, st.state, state)
    st.state = state
    st.changed_at = now
    if state in ("closed", "half_open"):
        st.successes = 0
    if state == "closed":
        st.failures = 0


def call(dependency: str, fn: Callable[[], T], now: Callable[[], datetime] = datetime.utcnow) -> T:
    """Run fn through the breaker. Raises DependencyUnavailable when open or when fn fails."""
    st = _get(dependency)
    t = now()
    with _lock:
        if st.state == "open":
            if t < st.changed_at + timedelta(seconds=st.cooldown_seconds):
                raise DependencyUnavailable(dependency, "circuit open")
            _transition(dependency, st, "half_open", t)
            changed = True
        else:
            changed = False
    if changed:
        _persist(dependency, st)
    try:
        result = fn()
    except Exception as exc:
        with _lock:
            st.failures += 1
            st.last_failure_at = t
            opened = st.state == "half_open" or st.failures >= st.failure_threshold
            if opened and st.state != "open":
                _transition(dependency, st, "open", t)
        if opened:
            _persist(dependency, st)
        raise DependencyUnavailable(dependency, f"{type(exc).__name__}: {exc}") from exc
    with _lock:
        closed = False
        if st.state == "half_open":
            st.successes += 1
            if st.successes >= st.half_open_max_calls:
                _transition(dependency, st, "closed", t)
                closed = True
        else:
            st.failures = 0
    if closed:
        _persist(dependency, st)
    return result


def states() -> dict[str, dict]:
    """Every known breaker: this instance's live state, else the last persisted state."""
    db = SessionLocal()
    try:
        out = {r.dependency: {"state": r.state or "closed", "failure_count": r.failure_count or 0,
                              "last_state_change_at": r.last_state_change_at.isoformat() if r.last_state_change_at
                              else None}
               for r in db.query(CircuitBreaker).all()}
    finally:
        db.close()
    with _lock:
        for dep, st in _states.items():
            out[dep] = {"state": st.state, "failure_count": st.failures,
                        "last_state_change_at": st.changed_at.isoformat()}
    return out


def reset(dependency: str) -> None:
    st = _get(dependency)
    with _lock:
        _transition(dependency, st, "closed", datetime.utcnow())
    _persist(dependency, st)


def forget() -> None:
    """Drop in-process state (tests); state reloads from the table on next use."""
    with _lock:
        _states.clear()
