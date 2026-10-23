/**
 * UI mirror of backend/app/permissions.py — the API is the authority and enforces every rule; this
 * copy only decides what to HIDE. Keep MATRIX identical to the backend's (same keys, same roles);
 * a route that is not listed needs only an authenticated analyst, exactly as on the server.
 */

export const ROLES = ['analyst', 'investigator', 'supervisor', 'admin'] as const;
export type Role = (typeof ROLES)[number];

const RANK: Record<string, number> = Object.fromEntries(ROLES.map((r, i) => [r, i]));

export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
/** A route as FastAPI declares it: method + path template, e.g. ['DELETE', '/api/v1/cases/{case_id}']. */
export type Route = readonly [Method, string];

const MATRIX: Record<string, Role> = {
  // --- investigator: case work beyond commenting ---
  'PATCH /api/v1/cases/{case_id}': 'investigator',
  'POST /api/v1/cases/check-sla': 'investigator',
  'POST /api/v1/cases/aggregate': 'investigator',
  'POST /api/v1/filings': 'investigator',
  'PATCH /api/v1/filings/{filing_id}': 'investigator', // submit/confirm needs supervisor (FILING_APPROVAL)
  'POST /api/v1/rules/{rule_id}/record-hit': 'investigator',
  'POST /api/v1/rules/{rule_id}/record-false-positive': 'investigator',
  'POST /api/v1/behavioral/update-baseline': 'investigator',
  // --- supervisor: approve, delete, read configuration / audit / privacy ---
  'DELETE /api/v1/transactions/{tx_id}': 'supervisor',
  'DELETE /api/v1/cases/{case_id}': 'supervisor',
  'DELETE /api/v1/filings/{filing_id}': 'supervisor',
  'POST /api/v1/rules/simulate': 'supervisor',
  'GET /api/v1/settings': 'supervisor',
  'GET /api/v1/flags': 'supervisor',
  'GET /api/v1/models': 'supervisor',
  'GET /api/v1/webhooks': 'supervisor',
  'POST /api/v1/privacy/dsar': 'supervisor',
  'GET /api/v1/privacy/pii-classification': 'supervisor',
  'GET /api/v1/privacy/requests': 'supervisor',
  'POST /api/v1/privacy/requests': 'supervisor',
  'GET /api/v1/privacy/requests/{request_id}': 'supervisor',
  'POST /api/v1/privacy/requests/{request_id}/execute': 'supervisor',
  'GET /api/v1/audit': 'supervisor',
  'GET /api/v1/audit/verify': 'supervisor',
  'GET /api/v1/audit/export': 'supervisor',
  // --- admin: configuration, users, billing ---
  'PUT /api/v1/settings/{key}': 'admin',
  'PUT /api/v1/flags/{key}': 'admin',
  'PATCH /api/v1/rules/{rule_id}': 'admin',
  'POST /api/v1/models': 'admin',
  'POST /api/v1/models/{version_id}/promote': 'admin',
  'POST /api/v1/health/circuit-breakers/{dependency}/reset': 'admin',
  'GET /api/v1/webhooks/subscriptions': 'admin',
  'POST /api/v1/webhooks/subscriptions': 'admin',
  'DELETE /api/v1/webhooks/subscriptions/{subscription_id}': 'admin',
  'POST /api/v1/webhooks/{event_id}/retry': 'admin',
  'GET /api/v1/admin/users': 'admin',
  'POST /api/v1/admin/users': 'admin',
  'PATCH /api/v1/admin/users/{user_id}': 'admin',
  'POST /api/v1/billing/subscribe': 'admin',
  'POST /api/v1/credits/checkout': 'admin',
  'PATCH /api/v1/billing/saved-card': 'admin',
  'DELETE /api/v1/billing/saved-card': 'admin',
  'POST /api/v1/credits/purchase': 'admin',
};

/** Checked inside the filings PATCH handler (backend/app/api/filings.py), not by the matrix. */
export const FILING_APPROVAL_ROLE: Role = 'supervisor';

export function requiredRole([method, path]: Route): Role {
  return MATRIX[`${method} ${path}`] ?? 'analyst';
}

export function hasRole(role: string | undefined | null, needed: Role): boolean {
  return role != null && (RANK[role] ?? -1) >= RANK[needed];
}

export function canCall(role: string | undefined | null, route: Route): boolean {
  return hasRole(role, requiredRole(route));
}
