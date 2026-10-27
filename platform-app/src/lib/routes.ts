import type { Route } from './permissions';

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  /** The API route the page is built on; the page (and its nav item) needs that route's role. */
  requires?: Route;
}

export const NAV_SECTIONS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: 'Overview',
    items: [
      { href: '/dashboard', icon: 'grid', label: 'Dashboard' },
      { href: '/transactions', icon: 'arrow-right-left', label: 'Transactions' },
      { href: '/cases', icon: 'folder', label: 'Cases' },
    ],
  },
  {
    label: 'Compliance',
    items: [
      { href: '/rules', icon: 'shield-check', label: 'Rules' },
      { href: '/filings', icon: 'document-text', label: 'Filings', requires: ['GET', '/api/v1/filings'] },
      { href: '/reports', icon: 'chart', label: 'Reports' },
    ],
  },
  {
    label: 'Governance',
    items: [
      { href: '/audit', icon: 'clipboard', label: 'Audit Trail', requires: ['GET', '/api/v1/audit'] },
      { href: '/approvals', icon: 'shield-check', label: 'Approvals', requires: ['GET', '/api/v1/change-requests'] },
      { href: '/privacy', icon: 'lock', label: 'Privacy Requests', requires: ['GET', '/api/v1/privacy/requests'] },
      { href: '/webhooks', icon: 'bolt', label: 'Webhooks', requires: ['GET', '/api/v1/webhooks'] },
    ],
  },
  {
    label: 'Developer',
    items: [
      { href: '/api-keys', icon: 'key', label: 'API Keys' },
      { href: '/docs', icon: 'book', label: 'API Docs' },
    ],
  },
  {
    label: 'Administration',
    items: [
      { href: '/operations', icon: 'server', label: 'Operations' },
      { href: '/users', icon: 'users', label: 'Users', requires: ['GET', '/api/v1/admin/users'] },
    ],
  },
  {
    label: 'Account',
    items: [
      { href: '/settings', icon: 'settings', label: 'Settings' },
    ],
  },
];

const ALL_ITEMS = NAV_SECTIONS.flatMap((s) => s.items);

/** The route a page path depends on (undefined: any signed-in user). */
export function pageRequirement(pathname: string): Route | undefined {
  return ALL_ITEMS.find((i) => pathname === i.href || pathname.startsWith(`${i.href}/`))?.requires;
}

/** Only same-site relative paths are valid post-login targets (no `//host`, no scheme, no backslash tricks). */
export function safeRedirect(target: string | null | undefined, fallback = '/dashboard'): string {
  if (!target || !target.startsWith('/') || target.startsWith('//') || target.includes('\\')) return fallback;
  if (/^\/(login|signup)(\/|\?|$)/.test(target)) return fallback;
  try {
    const url = new URL(target, 'http://same.origin');
    if (url.origin !== 'http://same.origin') return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}
