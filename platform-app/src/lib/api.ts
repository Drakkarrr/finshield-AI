/**
 * FinShield API Client
 * Communicates with the FastAPI backend at /api/*
 * Handles authentication tokens and all API endpoints.
 */

const API_BASE = '/api';

// ── Auth Types ──
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

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company: string | null;
  plan: string;
  credits_remaining: number;
  billing_cycle_start?: string | null;
  billing_cycle_end?: string | null;
  pending_plan_change?: string | null;
  is_trial?: boolean;
  trial_expires_at?: string | null;
  timezone?: string | null;
  saved_card_last4?: string | null;
  saved_card_expiry?: string | null;
  saved_card_holder?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company: string | null;
  plan: string;
  total_credits: number;
  used_credits: number;
  credits_remaining: number;
  created_at: string;
  billing_cycle_start?: string | null;
  billing_cycle_end?: string | null;
  pending_plan_change?: string | null;
  is_trial?: boolean;
  trial_expires_at?: string | null;
  timezone?: string | null;
  saved_card_last4?: string | null;
  saved_card_expiry?: string | null;
  saved_card_holder?: string | null;
}

// ── Transaction Types ──
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

export interface RagMatch {
  id: string;
  score?: number;
  similarity_score?: number;
  title?: string;
  name?: string;
  program?: string;
  decision?: string;
  case_summary?: string;
  content?: string;
  category?: string;
}

export interface RagContext {
  policies: RagMatch[];
  sanctions_matches: RagMatch[];
  similar_precedents: RagMatch[];
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
  created_at: string;
}

// ── Case Types ──
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

// ── Filing Types ──
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

// ── Other Types ──
export interface HealthData {
  status: string;
  version: string;
  services: Record<string, string>;
  uptime_seconds: number;
}

export interface CreditsData {
  total_credits: number;
  used_credits: number;
  remaining_credits: number;
  plan: string;
}

// ── Analytics / Stats ──
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
}

// ── Search ──
export interface SearchResultTx {
  id: string;
  amount: number;
  currency: string;
  sender: string;
  receiver: string;
  status: string;
  created_at: string;
}
export interface SearchResultCase {
  case_id: string;
  reason: string;
  status: string;
  priority: string;
  created_at: string;
}
export interface SearchResultKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
}
export interface SearchResults {
  query: string;
  transactions: SearchResultTx[];
  cases: SearchResultCase[];
  api_keys: SearchResultKey[];
}

// ── Notifications ──
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

// ── Case Comments ──
export interface CaseComment {
  id: string;
  body: string;
  user_id: string;
  created_at: string;
}

// ── Billing ─
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
}

export interface SubscribeResponse {
  plan: string;
  is_upgrade: boolean;
  effective: string;
  proration_usd: number;
  total_credits: number;
  credits_remaining: number;
  pending_plan_change: string | null;
  message: string;
}

export interface PurchaseResponse {
  credits_added: number;
  price_usd: number;
  total_credits: number;
  credits_remaining: number;
}

export interface CheckoutResponse {
  credits_added: number;
  price_usd: number;
  card_last4: string;
  total_credits: number;
  credits_remaining: number;
  status: string;
}

export interface ApiKeyData {
  id: string;
  name: string;
  key?: string;       // Only present on creation
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
}

// ── Token Management ──
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('finshield_token');
}

function setToken(token: string): void {
  localStorage.setItem('finshield_token', token);
}

function clearToken(): void {
  localStorage.removeItem('finshield_token');
  localStorage.removeItem('finshield_user');
}

// ── Core Request Function ──
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = '';
    try {
      // Read the response body once
      const text = await res.text();
      try {
        // Try to parse as JSON
        const body = JSON.parse(text);
        errorDetail = body.detail || body.detail?.message || JSON.stringify(body);
      } catch {
        // If not JSON, use the raw text
        errorDetail = text || res.statusText;
      }
    } catch {
      errorDetail = res.statusText || 'Unknown error';
    }
    throw new ApiError(res.status, errorDetail);
  }

  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

// ── API Methods ──
export const api = {
  // Auth
  register: (data: RegisterRequest) =>
    request<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  login: (data: LoginRequest) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  me: () => request<UserProfile>('/auth/me'),

  logout: () => {
    clearToken();
  },

  // Health
  health: () => request<HealthData>('/health'),

  // Transactions
  screenTransaction: (tx: TransactionRequest) =>
    request<TransactionResponse>('/v1/transactions', {
      method: 'POST',
      body: JSON.stringify(tx),
    }),

  listTransactions: (limit = 50, offset = 0) =>
    request<TransactionListItem[]>(`/v1/transactions?limit=${limit}&offset=${offset}`),

  // Cases
  createCase: (data: { transaction_id: string; reason: string; priority?: string }) =>
    request<CaseData>('/v1/cases', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getCase: (caseId: string) => request<CaseData>(`/v1/cases/${caseId}`),

  listCases: () => request<CaseData[]>('/v1/cases'),

  // Credits
  getCredits: () => request<CreditsData>('/v1/credits'),

  purchaseCredits: (credits: number) =>
    request<PurchaseResponse>('/v1/credits/purchase', {
      method: 'POST',
      body: JSON.stringify({ credits }),
    }),

  // Analytics
  getStats: () => request<StatsData>('/v1/stats'),

  // Rules
  listRules: () => request<RuleDefinition[]>('/v1/rules'),

  updateRule: (ruleId: string, data: { enabled?: boolean; custom_parameters?: Record<string, unknown> }) =>
    request<{ rule_id: string; enabled: boolean; custom_parameters: Record<string, unknown> | null; detail: string }>(`/v1/rules/${ruleId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Search
  search: (q: string) => request<SearchResults>(`/v1/search?q=${encodeURIComponent(q)}`),

  // Notifications
  listNotifications: (limit = 20, unreadOnly = false) =>
    request<NotificationListResponse>(`/v1/notifications?limit=${limit}&unread_only=${unreadOnly}`),

  markNotificationRead: (id: string) =>
    request<{ detail: string }>(`/v1/notifications/${id}/read`, { method: 'PATCH' }),

  markAllNotificationsRead: () =>
    request<{ detail: string }>('/v1/notifications/read-all', { method: 'POST' }),

  getNotificationPreferences: () => request<NotificationPreferences>('/v1/notifications/preferences'),

  updateNotificationPreferences: (data: Partial<NotificationPreferences>) =>
    request<{ detail: string }>('/v1/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Cases (extended)
  updateCase: (caseId: string, data: { status?: string; assigned_to?: string; priority?: string }) =>
    request<CaseData>(`/v1/cases/${caseId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  listCaseComments: (caseId: string) => request<CaseComment[]>(`/v1/cases/${caseId}/comments`),

  addCaseComment: (caseId: string, body: string) =>
    request<CaseComment>(`/v1/cases/${caseId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  // Profile
  updateProfile: (data: { first_name?: string; last_name?: string; company?: string; timezone?: string }) =>
    request<{ detail: string; first_name: string; last_name: string; company: string | null; timezone: string | null }>('/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  changePassword: (data: { current_password: string; new_password: string }) =>
    request<{ detail: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Billing
  checkoutCredits: (data: { credits: number; card_last4?: string; card_expiry?: string; card_holder?: string; use_saved_card?: boolean }) =>
    request<CheckoutResponse>('/v1/credits/checkout', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  savePaymentMethod: (data: { card_last4: string; card_expiry: string; card_holder: string }) =>
    request<{ detail: string; card_last4: string; card_expiry: string; card_holder: string }>('/v1/billing/saved-card', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  removePaymentMethod: () =>
    request<{ detail: string }>('/v1/billing/saved-card', {
      method: 'DELETE',
    }),

  // Billing
  listPlans: () => request<PlansResponse>('/v1/billing/plans'),

  subscribe: (planId: string) =>
    request<SubscribeResponse>('/v1/billing/subscribe', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId }),
    }),

  // API Keys
  createApiKey: (name: string) =>
    request<ApiKeyData>('/v1/keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  listApiKeys: () => request<ApiKeyData[]>('/v1/keys'),

  revokeApiKey: (keyId: string) =>
    request<{ detail: string }>(`/v1/keys/${keyId}`, {
      method: 'DELETE',
    }),

  // Transaction detail + delete + export
  getTransaction: (txId: string) =>
    request<TransactionDetail>(`/v1/transactions/${txId}`),

  deleteTransaction: (txId: string) =>
    request<{ deleted: string }>(`/v1/transactions/${txId}`, {
      method: 'DELETE',
    }),

  exportTransactions: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams({ fmt: 'csv' });
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    return `${API_BASE}/v1/transactions/export?${params.toString()}`;
  },

  // Case delete
  deleteCase: (caseId: string) =>
    request<{ deleted: string }>(`/v1/cases/${caseId}`, {
      method: 'DELETE',
    }),

  // Filings
  listFilings: (status?: string, filingType?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (filingType) params.set('filing_type', filingType);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<Filing[]>(`/v1/filings${query}`);
  },

  getFiling: (filingId: string) =>
    request<Filing>(`/v1/filings/${filingId}`),

  createFiling: (caseId: string, filingType: string, narrative?: string) =>
    request<Filing>('/v1/filings', {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId, filing_type: filingType, narrative }),
    }),

  updateFiling: (filingId: string, updates: { status?: string; narrative?: string; reference_number?: string }) =>
    request<Filing>(`/v1/filings/${filingId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  deleteFiling: (filingId: string) =>
    request<{ deleted: string }>(`/v1/filings/${filingId}`, {
      method: 'DELETE',
    }),

  // Token helpers
  getToken,
  setToken,
  clearToken,
};
