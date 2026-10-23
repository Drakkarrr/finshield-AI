"""Role-based access control (S3.1): one permission matrix, enforced by one dependency.

Roles are ordered: analyst < investigator < supervisor < admin. Every route on a protected router
runs `authorize`, which looks up (method, path template) in MATRIX; a route not listed needs only
an authenticated `analyst`. tests/test_permissions.py walks every registered route and checks the
matrix for all four roles, so a new route cannot silently skip the check.

  analyst       screen transactions, read everything in the tenant, create cases, comment / note
  investigator  + work cases (update, SLA sweep, aggregation), draft filings, hit / FP reporting
  supervisor    + approve: submit / confirm filings, delete records, read config, audit, privacy
  admin         + configure: settings, flags, rules, models, breakers, webhooks, users, billing
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.auth import get_current_user
from app.db_models import User

ROLES = ("analyst", "investigator", "supervisor", "admin")
RANK = {r: i for i, r in enumerate(ROLES)}

MATRIX: dict[tuple[str, str], str] = {
    # --- investigator: case work beyond commenting -------------------------------------------
    ("PATCH", "/api/v1/cases/{case_id}"): "investigator",
    ("POST", "/api/v1/cases/check-sla"): "investigator",
    ("POST", "/api/v1/cases/aggregate"): "investigator",
    ("POST", "/api/v1/filings"): "investigator",
    ("PATCH", "/api/v1/filings/{filing_id}"): "investigator",  # submit/confirm needs supervisor (in handler)
    ("POST", "/api/v1/rules/{rule_id}/record-hit"): "investigator",
    ("POST", "/api/v1/rules/{rule_id}/record-false-positive"): "investigator",
    ("POST", "/api/v1/behavioral/update-baseline"): "investigator",
    # --- supervisor: approve, delete, read configuration / audit / privacy -------------------
    ("DELETE", "/api/v1/transactions/{tx_id}"): "supervisor",
    ("DELETE", "/api/v1/cases/{case_id}"): "supervisor",
    ("DELETE", "/api/v1/filings/{filing_id}"): "supervisor",
    ("POST", "/api/v1/rules/simulate"): "supervisor",
    ("GET", "/api/v1/settings"): "supervisor",
    ("GET", "/api/v1/flags"): "supervisor",
    ("GET", "/api/v1/models"): "supervisor",
    ("GET", "/api/v1/webhooks"): "supervisor",
    ("POST", "/api/v1/privacy/dsar"): "supervisor",
    ("GET", "/api/v1/privacy/pii-classification"): "supervisor",
    ("GET", "/api/v1/privacy/requests"): "supervisor",
    ("POST", "/api/v1/privacy/requests"): "supervisor",
    ("GET", "/api/v1/privacy/requests/{request_id}"): "supervisor",
    ("POST", "/api/v1/privacy/requests/{request_id}/execute"): "supervisor",
    ("GET", "/api/v1/audit"): "supervisor",
    ("GET", "/api/v1/audit/verify"): "supervisor",
    ("GET", "/api/v1/audit/export"): "supervisor",
    # --- admin: configuration, users, billing ------------------------------------------------
    ("PUT", "/api/v1/settings/{key}"): "admin",
    ("PUT", "/api/v1/flags/{key}"): "admin",
    ("PATCH", "/api/v1/rules/{rule_id}"): "admin",
    ("POST", "/api/v1/models"): "admin",
    ("POST", "/api/v1/models/{version_id}/promote"): "admin",
    ("POST", "/api/v1/health/circuit-breakers/{dependency}/reset"): "admin",
    ("GET", "/api/v1/webhooks/subscriptions"): "admin",
    ("POST", "/api/v1/webhooks/subscriptions"): "admin",
    ("DELETE", "/api/v1/webhooks/subscriptions/{subscription_id}"): "admin",
    ("POST", "/api/v1/webhooks/{event_id}/retry"): "admin",
    ("GET", "/api/v1/admin/users"): "admin",
    ("POST", "/api/v1/admin/users"): "admin",
    ("PATCH", "/api/v1/admin/users/{user_id}"): "admin",
    ("POST", "/api/v1/billing/subscribe"): "admin",
    ("POST", "/api/v1/credits/checkout"): "admin",
    ("PATCH", "/api/v1/billing/saved-card"): "admin",
    ("DELETE", "/api/v1/billing/saved-card"): "admin",
    ("POST", "/api/v1/credits/purchase"): "admin",
}


def required_role(method: str, path: str) -> str:
    return MATRIX.get((method.upper(), path), "analyst")


def has_role(user: User, role: str) -> bool:
    return RANK.get(user.role, -1) >= RANK[role]


def require(user: User, role: str) -> None:
    if not has_role(user, role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires the {role} role")


def authorize(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """Router-level dependency: 403 unless the caller's role meets the route's requirement."""
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    require(current_user, required_role(request.method, path))
    return current_user
