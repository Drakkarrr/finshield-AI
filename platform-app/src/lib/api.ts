/**
 * FinShield API client.
 *
 * Every call goes same-origin to `/api/*`, which next.config.js rewrites to the FastAPI backend, so
 * the httpOnly `finshield_session` cookie (ruling D11) rides along. The browser never sees or stores
 * the token. Unsafe methods carry `X-Requested-With`, which the backend's CSRF check requires for
 * cookie-authenticated requests.
 */

const API_BASE = '/api';

// ── Auth / users ──
export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  company?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/** GET /api/auth/me */
export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company: string | null;
  role: string;
  tenant_id: string;
  plan: string;
  total_credits: number;
  used_credits: number;
  credits_remaining: number;
  created_at: string;
  billing_cycle_start: string | null;
  billing_cycle_end: string | null;
  pending_plan_change: string | null;
  is_trial: boolean;
  trial_expires_at: string | null;
  timezone: string | null;
}

export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

// ── Transactions ──
export interface TransactionRequest {
  amount: number;
  currency: string;
  transaction_type: 'wire' | 'ach' | 'card' | 'international' | 'crypto' | 'p2p';
  sender_name: string;
  receiver_name: string;
  sender_id?: string;
  receiver_id?: string;
  destination_country?: string;
  description?: string;
  idempotency_key?: string;
}

export interface RuleResult {
  rule_id: string;
  rule_type: string;
  rule_name: string;
  triggered: boolean;
  detail: string | null;
  latency_ms: number;
}

export interface ScreeningResult {
  transaction_id: string;
  idempotency_key: string;
  status: 'approved' | 'flagged' | 'blocked' | 'in_review' | 'pending';
  risk_score: number;
  credit_tier: 'rule_only' | 'behavioral' | 'full_ml';
  credits_consumed: number;
  rule_results: RuleResult[];
  behavioral_score: number | null;
  ml_classification: string | null;
  ml_confidence: number | null;
  total_latency_ms: number;
  timestamp: string;
  pipeline_stages: string[];
}

export interface TransactionResponse {
  success: boolean;
  data: ScreeningResult | null;
  error: string | null;
}

export interface TransactionListItem {
  id: string;
  amount: number;
  currency: string;
  type: string;
  sender: string;
  receiver: string;
  status: string;
  risk_score: number;
  credit_tier: string;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface RagMatch {
  id: string;
  score?: number;
  similarity_score?: number;
  title?: string;
  name?: string;
  program?: string;
  decision?: string;
  case_summary?: string;
}

export interface RagContext {
  policies: RagMatch[];
  sanctions_matches: RagMatch[];
  similar_precedents: RagMatch[];
}

export interface DecisionReason {
  source: string;
  feature: string;
  value?: unknown;
  contribution: number;
  detail?: string | null;
  rule_id?: string;
}

export interface TransactionDetail {
  id: string;
  amount: number;
  currency: string;
  transaction_type: string;
  sender_name: string;
  receiver_name: string;
  destination_country: string | null;
  status: string;
  risk_score: number;
  credit_tier: string;
  credits_consumed: number;
  idempotency_key: string;
  rule_results: RuleResult[];
  behavioral_score: number | null;
  ml_classification: string | null;
  ml_confidence: number | null;
  total_latency_ms: number | null;
  pipeline_stages: string[];
  rag_context: RagContext | null;
  account_id: string | null;
  reasons: DecisionReason[];
  model_version: string | null;
  degraded: boolean;
  created_at: string;
}

export interface BehavioralBaseline {
  account_id: string;
  exists: boolean;
  baseline: {
    avg_amount: number;
    std_dev_amount: number;
    max_amount: number;
    min_amount: number;
    total_transactions: number;
    history_days: number;
    is_cold_start: boolean;
    typical_countries: string[] | null;
    typical_payees: string[] | null;
    typical_tx_types: string[] | null;
    last_computed_at: string;
  } | null;
}

// ── Cases ──
export interface CaseData {
  case_id: string;
  transaction_id: string;
  status: string;
  priority: string;
  reason: string;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseComment {
  id: string;
  body: string;
  user_id: string;
  created_at: string;
}

export interface CaseNote {
  id: string;
  note: string;
  user_id: string;
  created_at: string;
}

export interface SlaSweepResult {
  escalated: number;
  approaching_notified: number;
}

// ── Filings ──
export interface Filing {
  id: string;
  case_id: string;
  filing_type: string;
  status: string;
  deadline: string | null;
  narrative: string | null;
  structured_data: Record<string, unknown> | null;
  reference_number: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  created_at: string;
  updated_at: string;
}

// ── Health / stats ──
export interface HealthData {
  status: string;
  version: string;
  services: Record<string, string>;
  uptime_seconds: number;
}

export interface StatsData {
  total_transactions: number;
  approved: number;
  flagged: number;
  blocked: number;
  in_review: number;
  open_cases: number;
  avg_risk_score: number;
  credits_used: number;
  credits_remaining: number;
}

export interface BreakerState {
  dependency: string;
  state: 'closed' | 'half_open' | 'open';
  failure_count: number;
  last_state_change_at: string | null;
}

export interface OverallHealth {
  health: 'green' | 'yellow' | 'red';
  message: string;
  breakers_summary: Record<string, number>;
}

export interface ListsStatus {
  max_age_hours: number;
  sources: Array<{
    source: string;
    list_type: string;
    list_version: string;
    entry_count: number;
    imported_at: string;
    age_hours: number;
    stale: boolean;
    is_fixture: boolean;
  }>;
  sanctions_loaded: boolean;
  pep_loaded: boolean;
  high_risk_countries: string[];
}

export interface RuntimeSetting {
  key: string;
  value: unknown;
  default: unknown;
  description: string;
  source: 'override' | 'default';
  updated_by: string | null;
  updated_at?: string | null;
}

export interface FeatureFlag {
  key: string;
  enabled: boolean;
  default: boolean;
  description: string;
  source: 'override' | 'default';
  updated_by: string | null;
}

export interface ModelVersion {
  id: string;
  label: string;
  name: string;
  version: number;
  kind: string;
  status: string;
  metrics: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string | null;
  activated_at: string | null;
}

// ── Rules ──
export interface RuleDefinition {
  rule_id: string;
  rule_type: string;
  name: string;
  description: string;
  enabled: boolean;
  action: string;
  parameters: Record<string, unknown>;
  metadata?: { list_size?: number; editable?: boolean };
  is_customized?: boolean;
  priority?: number;
  version?: number;
}

export interface RuleSimulation {
  rule_id: string;
  rule_name: string;
  days_simulated: number;
  transactions_tested: number;
  triggered_count: number;
  would_block: number;
  would_flag: number;
  trigger_rate: number;
}

export interface RuleStats {
  rule_id: string;
  hit_count: number;
  false_positive_count: number;
  last_hit_at: string | null;
  false_positive_rate: number;
}

// ── Search / notifications ──
export interface SearchResults {
  query: string;
  transactions: Array<{ id: string; amount: number; currency: string; sender: string; receiver: string; status: string; created_at: string }>;
  cases: Array<{ case_id: string; reason: string; status: string; priority: string; created_at: string }>;
  api_keys: Array<{ id: string; name: string; key_prefix: string; is_active: boolean }>;
}

export interface NotificationData {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  link: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationData[];
  unread_count: number;
}

export interface NotificationPreferences {
  email_blocked_tx: boolean;
  email_new_cases: boolean;
  email_daily_summary: boolean;
  email_weekly_report: boolean;
  email_system_downtime: boolean;
  email_credit_alerts: boolean;
}

// ── Billing ──
export interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  included_credits: number | null;
  features: string[];
}

export interface PlansResponse {
  plans: Plan[];
  current_plan: string;
  billing_cycle_start: string | null;
  billing_cycle_end: string | null;
  days_remaining: number | null;
  pending_plan_change: string | null;
  is_trial: boolean;
  trial_expires_at: string | null;
  credit_packs: Array<{ credits: number; price_usd: number }>;
  /** "simulated": development mode, no real payment is taken. */
  payments_mode: 'stripe' | 'simulated';
}

export interface SubscribeResponse {
  plan: string;
  message: string;
  total_credits: number;
  credits_remaining: number;
  pending_plan_change: string | null;
}

/** "stripe": send the browser to Stripe Checkout. "simulated": credits were added without payment. */
export type CheckoutResponse =
  | { mode: 'stripe'; checkout_url: string; session_id: string }
  | { mode: 'simulated'; credits_added: number; price_usd: number; total_credits: number; credits_remaining: number; status: string };

// ── API keys ──
export interface ApiKeyData {
  id: string;
  name: string;
  key?: string; // only present on creation
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
}

// ── Webhooks ──
export interface WebhookSubscription {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_by: string | null;
  created_at: string | null;
}

export interface CreatedWebhookSubscription extends WebhookSubscription {
  secret: string;
  event_types: string[];
}

export interface WebhookEvent {
  id: string;
  subscription_id: string;
  event_type: string;
  payload: unknown;
  status: string;
  attempts: number;
  response_code: number | null;
  last_error: string | null;
  next_retry_at: string | null;
  attempt_log: unknown[];
  created_at: string | null;
  delivered_at: string | null;
}

// ── Audit ──
export interface AuditEntry {
  id: string;
  seq: number | null;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: unknown;
  ip_address: string | null;
  created_at: string | null;
  prev_hash: string | null;
  entry_hash: string | null;
  sealed: boolean;
}

export interface AuditVerification {
  ok: boolean;
  verified: number;
  first_break_seq: number | null;
  head_hash?: string;
  entry_id?: string;
  detail?: string;
  pending: number;
}

export interface AuditFilters {
  actor?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  date_from?: string;
  date_to?: string;
}

// ── Privacy ──
export interface PrivacyRequest {
  id: string;
  subject_type: 'customer' | 'user';
  subject_ref_masked: string;
  request_type: 'access' | 'erasure';
  status: string;
  received_at: string;
  due_at: string;
  overdue: boolean;
  completed_at: string | null;
  handled_by: string | null;
  legal_basis_notes: string | null;
  outcome?: unknown;
}

// ── OpenAPI (only the parts the docs page renders) ──
export interface OpenAPIOperation {
  summary?: string;
  description?: string;
  tags?: string[];
  operationId?: string;
  deprecated?: boolean;
}

export interface OpenAPIDocument {
  openapi: string;
  info: { title: string; version: string; description?: string };
  paths: Record<string, Record<string, OpenAPIOperation | unknown>>;
}

// ── Transport ──
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

function errorDetail(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    // FastAPI 422: [{loc: ['body', 'field'], msg}]
    return detail
      .map((e: { loc?: unknown[]; msg?: string }) => [e.loc?.slice(1).join('.'), e.msg].filter(Boolean).join(': '))
      .join('; ');
  }
  return fallback;
}

let expiring = false;

/** A session that dies mid-use (cookie expired / revoked): clear the cookie, go to login, come back. */
function sessionExpired() {
  if (typeof window === 'undefined' || expiring) return;
  expiring = true;
  const back = window.location.pathname + window.location.search;
  fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' }, keepalive: true })
    .catch(() => undefined)
    // Outside React (no router here), and a full load drops the dead session's cached data.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    .finally(() => window.location.assign(`/login?expired=1&redirect=${encodeURIComponent(back)}`));
}

interface SendOptions {
  /**
   * What a 401 means. 'expire' (default): the session ended mid-use. 'throw': the caller handles it
   * (login with a wrong password, the initial "am I signed in?" probe).
   */
  on401?: 'expire' | 'throw';
}

async function send(path: string, init: RequestInit = {}, { on401 = 'expire' }: SendOptions = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (method !== 'GET' && method !== 'HEAD') headers.set('X-Requested-With', 'XMLHttpRequest');

  const res = await fetch(`${API_BASE}${path}`, { ...init, method, headers, credentials: 'same-origin' });
  if (res.ok) return res;

  const text = await res.text().catch(() => '');
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { /* not JSON */ }
  const message = errorDetail(body, text || res.statusText || `HTTP ${res.status}`);

  if (res.status === 401 && on401 === 'expire') {
    sessionExpired();
    throw new ApiError(401, 'Your session has expired. Redirecting to sign in…');
  }
  throw new ApiError(res.status, message);
}

async function request<T>(path: string, init?: RequestInit, opts?: SendOptions): Promise<T> {
  const res = await send(path, init, opts);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)); });
  const s = q.toString();
  return s ? `?${s}` : '';
}

const enc = encodeURIComponent;

// ── Endpoints ──
export const api = {
  // Auth (session cookie is set / cleared by the backend)
  register: (data: RegisterRequest) => request<unknown>('/auth/register', json('POST', data), { on401: 'throw' }),
  login: (data: LoginRequest) => request<unknown>('/auth/login', json('POST', data), { on401: 'throw' }),
  logout: () => request<void>('/auth/logout', json('POST'), { on401: 'throw' }),
  me: () => request<UserProfile>('/auth/me', undefined, { on401: 'throw' }),
  updateProfile: (data: { first_name?: string; last_name?: string; company?: string; timezone?: string }) =>
    request<{ detail: string }>('/auth/me', json('PATCH', data)),
  changePassword: (data: { current_password: string; new_password: string }) =>
    request<{ detail: string }>('/auth/change-password', json('POST', data)),

  // The backend's live OpenAPI document (public, served through the same /api proxy)
  openapi: () => request<OpenAPIDocument>('/openapi.json'),

  // Health / stats
  health: () => request<HealthData>('/health'),
  overallHealth: () => request<OverallHealth>('/v1/health/overall'),
  circuitBreakers: () => request<{ breakers: BreakerState[] }>('/v1/health/circuit-breakers'),
  resetBreaker: (dependency: string) =>
    request<{ dependency: string; state: string }>(`/v1/health/circuit-breakers/${enc(dependency)}/reset`, json('POST')),
  getStats: () => request<StatsData>('/v1/stats'),
  listsStatus: () => request<ListsStatus>('/v1/lists/status'),

  // Transactions
  screenTransaction: (tx: TransactionRequest) => request<TransactionResponse>('/v1/transactions', json('POST', tx)),
  listTransactions: async (limit: number, offset: number): Promise<Page<TransactionListItem>> => {
    const res = await send(`/v1/transactions${query({ limit, offset })}`);
    const items = (await res.json()) as TransactionListItem[];
    const header = res.headers.get('X-Total-Count');
    return { items, total: header !== null ? Number(header) : offset + items.length };
  },
  getTransaction: (txId: string) => request<TransactionDetail>(`/v1/transactions/${enc(txId)}`),
  deleteTransaction: (txId: string) => request<{ pseudonymised: string }>(`/v1/transactions/${enc(txId)}`, json('DELETE')),
  exportTransactionsUrl: (startDate?: string, endDate?: string) =>
    `${API_BASE}/v1/transactions/export${query({ fmt: 'csv', start_date: startDate, end_date: endDate })}`,
  behavioralBaseline: (accountId: string) => request<BehavioralBaseline>(`/v1/behavioral/baseline/${enc(accountId)}`),

  // Cases
  listCases: () => request<CaseData[]>('/v1/cases'),
  createCase: (data: { transaction_id: string; reason: string; priority?: string }) =>
    request<CaseData>('/v1/cases', json('POST', data)),
  updateCase: (caseId: string, data: { status?: string; assigned_to?: string; priority?: string }) =>
    request<CaseData>(`/v1/cases/${enc(caseId)}`, json('PATCH', data)),
  deleteCase: (caseId: string) => request<{ deleted: string }>(`/v1/cases/${enc(caseId)}`, json('DELETE')),
  listCaseComments: (caseId: string) => request<CaseComment[]>(`/v1/cases/${enc(caseId)}/comments`),
  addCaseComment: (caseId: string, body: string) =>
    request<CaseComment>(`/v1/cases/${enc(caseId)}/comments`, json('POST', { body })),
  listCaseNotes: (caseId: string) => request<CaseNote[]>(`/v1/cases/${enc(caseId)}/notes`),
  addCaseNote: (caseId: string, note: string) => request<CaseNote>(`/v1/cases/${enc(caseId)}/notes`, json('POST', { note })),
  checkSla: () => request<SlaSweepResult>('/v1/cases/check-sla', json('POST')),
  /** Attach to an open case for the same sender, or open a new one (query parameters, not a body). */
  aggregateCase: (data: { transaction_id: string; reason: string; priority: string }) =>
    request<{ aggregated: boolean; case_id: string; message: string }>(`/v1/cases/aggregate${query(data)}`, json('POST')),

  // Filings
  listFilings: (status?: string, filingType?: string) =>
    request<Filing[]>(`/v1/filings${query({ status, filing_type: filingType })}`),
  createFiling: (caseId: string, filingType: string, narrative?: string) =>
    request<Filing>('/v1/filings', json('POST', { case_id: caseId, filing_type: filingType, narrative })),
  updateFiling: (filingId: string, updates: { status?: string; narrative?: string; reference_number?: string }) =>
    request<Filing>(`/v1/filings/${enc(filingId)}`, json('PATCH', updates)),
  deleteFiling: (filingId: string) => request<{ deleted: string }>(`/v1/filings/${enc(filingId)}`, json('DELETE')),

  // Rules
  listRules: () => request<RuleDefinition[]>('/v1/rules'),
  updateRule: (ruleId: string, data: { enabled?: boolean; custom_parameters?: Record<string, unknown> }) =>
    request<{ rule_id: string; detail: string }>(`/v1/rules/${enc(ruleId)}`, json('PATCH', data)),
  simulateRule: (ruleId: string, days: number) =>
    request<RuleSimulation>('/v1/rules/simulate', json('POST', { rule_id: ruleId, days })),
  ruleStats: (ruleId: string) => request<RuleStats>(`/v1/rules/${enc(ruleId)}/stats`),

  // Search / notifications
  search: (q: string) => request<SearchResults>(`/v1/search${query({ q })}`),
  listNotifications: (limit = 20, unreadOnly = false) =>
    request<NotificationListResponse>(`/v1/notifications${query({ limit, unread_only: unreadOnly })}`),
  markNotificationRead: (id: string) => request<{ detail: string }>(`/v1/notifications/${enc(id)}/read`, json('PATCH')),
  markAllNotificationsRead: () => request<{ detail: string }>('/v1/notifications/read-all', json('POST')),
  getNotificationPreferences: () => request<NotificationPreferences>('/v1/notifications/preferences'),
  updateNotificationPreferences: (data: Partial<NotificationPreferences>) =>
    request<{ detail: string }>('/v1/notifications/preferences', json('PUT', data)),

  // Billing
  listPlans: () => request<PlansResponse>('/v1/billing/plans'),
  subscribe: (planId: string) => request<SubscribeResponse>('/v1/billing/subscribe', json('POST', { plan_id: planId })),
  checkoutCredits: (credits: number) => request<CheckoutResponse>('/v1/credits/checkout', json('POST', { credits })),

  // API keys
  listApiKeys: () => request<ApiKeyData[]>('/v1/keys'),
  createApiKey: (name: string) => request<ApiKeyData>('/v1/keys', json('POST', { name })),
  revokeApiKey: (keyId: string) => request<{ detail: string }>(`/v1/keys/${enc(keyId)}`, json('DELETE')),

  // Admin: users
  listUsers: () => request<AdminUser[]>('/v1/admin/users'),
  createUser: (data: { email: string; password: string; first_name: string; last_name: string; role: string }) =>
    request<AdminUser>('/v1/admin/users', json('POST', data)),
  updateUser: (userId: string, data: { role?: string; is_active?: boolean }) =>
    request<AdminUser>(`/v1/admin/users/${enc(userId)}`, json('PATCH', data)),

  // Webhooks
  listWebhookSubscriptions: () => request<WebhookSubscription[]>('/v1/webhooks/subscriptions'),
  createWebhookSubscription: (url: string, events: string[]) =>
    request<CreatedWebhookSubscription>('/v1/webhooks/subscriptions', json('POST', { url, events })),
  deleteWebhookSubscription: (id: string) =>
    request<{ id: string; active: boolean }>(`/v1/webhooks/subscriptions/${enc(id)}`, json('DELETE')),
  listWebhookEvents: (params: { status?: string; event_type?: string; limit: number; offset: number }) =>
    request<{ total: number; items: WebhookEvent[] }>(`/v1/webhooks${query(params)}`),
  retryWebhookEvent: (eventId: string) => request<WebhookEvent>(`/v1/webhooks/${enc(eventId)}/retry`, json('POST')),

  // Audit
  listAudit: (filters: AuditFilters & { limit: number; offset: number }) =>
    request<{ total: number; limit: number; offset: number; items: AuditEntry[] }>(`/v1/audit${query({ ...filters })}`),
  verifyAudit: () => request<AuditVerification>('/v1/audit/verify'),
  exportAudit: () => request<Record<string, unknown> & { count: number }>('/v1/audit/export'),
  auditPublicKey: () => request<{ algorithm: string; public_key: string }>('/v1/audit/public-key'),

  // Privacy (data-subject requests)
  listPrivacyRequests: () => request<PrivacyRequest[]>('/v1/privacy/requests'),
  getPrivacyRequest: (id: string) => request<PrivacyRequest>(`/v1/privacy/requests/${enc(id)}`),
  createPrivacyRequest: (data: { subject_type: 'customer' | 'user'; subject_ref: string; request_type: 'access' | 'erasure'; legal_basis_notes?: string }) =>
    request<PrivacyRequest>('/v1/privacy/requests', json('POST', data)),
  executePrivacyRequest: (id: string) => request<PrivacyRequest>(`/v1/privacy/requests/${enc(id)}/execute`, json('POST')),

  // Runtime configuration
  listSettings: () => request<RuntimeSetting[]>('/v1/settings'),
  updateSetting: (key: string, value: unknown) =>
    request<{ key: string; value: unknown }>(`/v1/settings/${enc(key)}`, json('PUT', { value })),
  listFlags: () => request<FeatureFlag[]>('/v1/flags'),
  updateFlag: (key: string, enabled: boolean) =>
    request<{ key: string; enabled: boolean }>(`/v1/flags/${enc(key)}`, json('PUT', { enabled })),
  listModels: () => request<ModelVersion[]>('/v1/models'),
  promoteModel: (versionId: string) => request<ModelVersion>(`/v1/models/${enc(versionId)}/promote`, json('POST')),
};

/** Message for a caught error; 403 says which role is missing (the backend's detail names it). */
export function errorMessage(e: unknown, fallback = 'Something went wrong.'): string {
  if (e instanceof ApiError) return e.message || fallback;
  if (e instanceof Error) return e.message || fallback;
  return fallback;
}
