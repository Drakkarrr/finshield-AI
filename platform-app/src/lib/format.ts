/**
 * Production-grade formatting utilities.
 * Locale-aware, timezone-aware, currency-aware.
 */

// Detect user locale (falls back to en-US)
export const USER_LOCALE =
  typeof navigator !== 'undefined'
    ? navigator.language || 'en-US'
    : 'en-US';

// Detect user timezone
export const USER_TIMEZONE =
  typeof Intl !== 'undefined' && Intl.DateTimeFormat
    ? Intl.DateTimeFormat().resolvedOptions().timeZone
    : 'UTC';

// ── Currency ──
export function formatCurrency(
  amount: number,
  currency: string = 'USD',
  locale: string = USER_LOCALE,
): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

// ── Numbers ──
export function formatNumber(
  value: number,
  locale: string = USER_LOCALE,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

// ── Dates ──
export function formatDate(
  iso: string,
  locale: string = USER_LOCALE,
  timeZone: string = USER_TIMEZONE,
): string {
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone,
  }).format(new Date(iso));
}

export function formatDateTime(
  iso: string,
  locale: string = USER_LOCALE,
  timeZone: string = USER_TIMEZONE,
): string {
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
    hour12: true,
  }).format(new Date(iso));
}

export function formatTime(
  iso: string,
  locale: string = USER_LOCALE,
  timeZone: string = USER_TIMEZONE,
): string {
  return new Intl.DateTimeFormat(locale, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone,
    hour12: true,
  }).format(new Date(iso));
}

// ── Relative time (timeAgo) ──
export function timeAgo(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = now - then;

  if (diff < 0) return 'just now';
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

// ── Credits progress ──
export interface CreditsInfo {
  total: number;
  used: number;
  remaining: number;
  pctUsed: number;
  pctRemaining: number;
}

export function calcCredits(total: number, used: number): CreditsInfo {
  const remaining = Math.max(0, total - used);
  const pctUsed = total > 0 ? Math.round((used / total) * 100) : 0;
  const pctRemaining = total > 0 ? Math.round((remaining / total) * 100) : 0;
  return { total, used, remaining, pctUsed, pctRemaining };
}

// ── Timezone label ──
export function timezoneLabel(tz: string): string {
  // Convert "America/New_York" → "EDT" or "EST"
  try {
    const formatter = new Intl.DateTimeFormat(USER_LOCALE, {
      timeZone: tz,
      timeZoneName: 'short',
    });
    const parts = formatter.formatToParts(new Date());
    return parts.find((p) => p.type === 'timeZoneName')?.value || tz;
  } catch {
    return tz;
  }
}

// ── Country code → name (simple map for common codes) ──
const COUNTRY_NAMES: Record<string, string> = {
  US: 'United States', GB: 'United Kingdom', CN: 'China', RU: 'Russia',
  KP: 'North Korea', IR: 'Iran', SY: 'Syria', CU: 'Cuba', PH: 'Philippines',
  JP: 'Japan', DE: 'Germany', FR: 'France', SG: 'Singapore', HK: 'Hong Kong',
  AE: 'UAE', IN: 'India', BR: 'Brazil', MX: 'Mexico', CA: 'Canada',
  AU: 'Australia', KR: 'South Korea', MY: 'Malaysia', TH: 'Thailand',
  VN: 'Vietnam', ID: 'Indonesia',
};

export function countryName(code: string): string {
  return COUNTRY_NAMES[code.toUpperCase()] || code.toUpperCase();
}
