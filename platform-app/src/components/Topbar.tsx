'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { useAuth } from '@/contexts/AuthContext';
import { api, SearchResults } from '@/lib/api';
import { Modal, StatusBadge } from '@/components/ui';
import { formatCurrency, formatNumber, timeAgo, trialDaysLeft } from '@/lib/format';

// ── Search ──
function SearchDialog({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (query.length < 2) return;
    const timeout = setTimeout(async () => {
      setLoading(true);
      try { setResults(await api.search(query)); } catch { setResults(null); }
      setLoading(false);
    }, 300);
    return () => clearTimeout(timeout);
  }, [query]);

  const go = (href: string) => { router.push(href); onClose(); };
  const total = results ? results.transactions.length + results.cases.length + results.api_keys.length : 0;
  const row = 'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-bg-alt transition-colors text-left';

  return (
    <Modal open onClose={onClose} title="Search" size="xl">
      <label htmlFor="global-search" className="sr-only">Search transactions, cases and API keys</label>
      <input
        id="global-search"
        data-autofocus
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search transactions, cases, API keys…"
        className="w-full bg-surface border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder:text-ink-light focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
      />
      <div className="mt-3 max-h-80 overflow-y-auto" aria-live="polite">
        {query.length < 2 ? (
          <p className="p-4 text-center text-sm text-ink-muted">Type at least 2 characters to search.</p>
        ) : loading ? (
          <p className="p-4 text-center text-sm text-ink-muted">Searching…</p>
        ) : total === 0 ? (
          <p className="p-4 text-center text-sm text-ink-muted">No results for &quot;{query}&quot;.</p>
        ) : results && (
          <div className="space-y-2">
            {results.transactions.length > 0 && (
              <section>
                <h3 className="px-3 py-1.5 text-2xs font-semibold text-ink-muted uppercase tracking-wider">Transactions</h3>
                {results.transactions.map((tx) => (
                  <button key={tx.id} type="button" onClick={() => go('/transactions')} className={row}>
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm text-ink truncate">{formatCurrency(tx.amount, tx.currency)} — {tx.sender} → {tx.receiver}</span>
                      <span className="block text-2xs text-ink-muted">{timeAgo(tx.created_at)}</span>
                    </span>
                    <StatusBadge status={tx.status} />
                  </button>
                ))}
              </section>
            )}
            {results.cases.length > 0 && (
              <section>
                <h3 className="px-3 py-1.5 text-2xs font-semibold text-ink-muted uppercase tracking-wider">Cases</h3>
                {results.cases.map((c) => (
                  <button key={c.case_id} type="button" onClick={() => go('/cases')} className={row}>
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm text-ink truncate">{c.case_id} — {c.reason}</span>
                      <span className="block text-2xs text-ink-muted">{c.priority} priority</span>
                    </span>
                    <StatusBadge status={c.status} />
                  </button>
                ))}
              </section>
            )}
            {results.api_keys.length > 0 && (
              <section>
                <h3 className="px-3 py-1.5 text-2xs font-semibold text-ink-muted uppercase tracking-wider">API Keys</h3>
                {results.api_keys.map((k) => (
                  <button key={k.id} type="button" onClick={() => go('/api-keys')} className={row}>
                    <span className="flex-1 text-sm text-ink">{k.name}</span>
                    <span className="text-xs text-ink-muted font-mono">{k.key_prefix}••••</span>
                    <StatusBadge status={k.is_active ? 'active' : 'revoked'} label={k.is_active ? 'Active' : 'Revoked'} />
                  </button>
                ))}
              </section>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Notifications ──
function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  // Unread badge: polled every 30 s while the tab is visible (SWR pauses polling in hidden tabs).
  const { data: unread, mutate: refreshUnread } = useSWR('notifications:unread', () => api.listNotifications(1, true), { refreshInterval: 30_000 });
  const { data, isLoading, mutate } = useSWR(open ? 'notifications:list' : null, () => api.listNotifications(15));
  const unreadCount = unread?.unread_count ?? 0;

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onClick); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const refresh = () => { mutate(); refreshUnread(); };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="notifications-panel"
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
        className="relative p-2 rounded-lg text-ink-muted hover:text-ink hover:bg-bg-alt transition-colors"
      >
        <svg className="w-5 h-5" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span aria-hidden="true" className="absolute top-1 right-1 min-w-4 h-4 px-1 bg-accent rounded-full text-2xs text-navy font-bold flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div id="notifications-panel" className="absolute right-0 top-full mt-2 w-80 bg-surface border border-border rounded-xl shadow-dropdown overflow-hidden z-dropdown">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-light">
            <h2 className="text-sm font-semibold text-ink">Notifications</h2>
            {(data?.unread_count ?? 0) > 0 && (
              <button type="button" onClick={async () => { await api.markAllNotificationsRead(); refresh(); }} className="text-2xs text-accent-fg hover:underline font-medium">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto">
            {isLoading ? (
              <p className="p-6 text-center text-sm text-ink-muted">Loading…</p>
            ) : !data || data.notifications.length === 0 ? (
              <p className="p-6 text-center text-sm text-ink-muted">No notifications.</p>
            ) : (
              <ul>
                {data.notifications.map((n) => (
                  <li key={n.id} className={`px-4 py-3 border-b border-border-light last:border-0 ${!n.is_read ? 'bg-warning-bg' : ''}`}>
                    <p className="text-xs font-semibold text-ink">
                      {n.title}
                      {!n.is_read && <span className="ml-2 text-2xs font-medium text-warning-fg">Unread</span>}
                    </p>
                    <p className="text-2xs text-ink-secondary mt-0.5 leading-relaxed">{n.message}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-2xs">
                      <span className="text-ink-muted">{timeAgo(n.created_at)}</span>
                      {n.link && <Link href={n.link} className="font-medium hover:underline" onClick={() => setOpen(false)}>View</Link>}
                      {!n.is_read && (
                        <button type="button" onClick={async () => { await api.markNotificationRead(n.id); refresh(); }} className="text-ink-muted hover:text-ink">
                          Mark read
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TrialBadge({ expiresAt }: { expiresAt: string }) {
  const daysLeft = trialDaysLeft(expiresAt);
  const tone = daysLeft === 0
    ? 'bg-danger-bg text-danger-fg border-danger-light'
    : daysLeft <= 3 ? 'bg-warning-bg text-warning-fg border-warning-light' : 'bg-info-bg text-info-fg border-info-light';
  return (
    <Link href="/settings?tab=billing" className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border ${tone}`}>
      {daysLeft === 0 ? 'Trial expired — Upgrade' : `Trial: ${daysLeft} day${daysLeft === 1 ? '' : 's'} left`}
    </Link>
  );
}

export default function Topbar() {
  const { user, logout } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} />}

      <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-6 sticky top-0 z-topbar">
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 bg-bg rounded-lg px-3 py-2 flex-1 hover:bg-bg-alt border border-border-light hover:border-border transition-colors text-left"
          >
            <svg className="w-4 h-4 text-ink-muted shrink-0" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <span className="text-sm text-ink-muted flex-1">Search transactions, cases…</span>
            <kbd className="hidden sm:inline text-2xs text-ink-muted bg-surface px-1.5 py-0.5 rounded border border-border-light">Ctrl K</kbd>
          </button>
        </div>

        <div className="flex items-center gap-4">
          {user?.is_trial && user.trial_expires_at && <TrialBadge expiresAt={user.trial_expires_at} />}

          <p className="hidden sm:flex items-center gap-1.5 bg-warning-bg border border-warning-light rounded-lg px-3 py-1.5 text-sm">
            <span className="font-semibold text-warning-fg">{formatNumber(user?.credits_remaining ?? 0)}</span>
            <span className="text-2xs text-ink-muted">credits</span>
          </p>

          <Notifications />

          <div className="flex items-center gap-2.5">
            <span aria-hidden="true" className="w-8 h-8 rounded-full bg-navy flex items-center justify-center text-accent text-xs font-bold">
              {user?.first_name?.charAt(0) || 'U'}
            </span>
            <div className="hidden md:block">
              <p className="text-sm font-medium text-ink">{user ? `${user.first_name} ${user.last_name}` : ''}</p>
              <p className="text-2xs text-ink-muted">{[user?.company, user?.role].filter(Boolean).join(' · ')}</p>
            </div>
            <button
              type="button"
              onClick={() => logout()}
              className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-bg-alt transition-colors"
              aria-label="Sign out"
              title="Sign out"
            >
              <svg className="w-4 h-4" aria-hidden="true" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
            </button>
          </div>
        </div>
      </header>
    </>
  );
}
