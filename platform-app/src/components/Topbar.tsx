'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { api, SearchResults, NotificationListResponse } from '@/lib/api';
import { formatCurrency, formatNumber, formatDateTime, timeAgo, timezoneLabel, USER_TIMEZONE } from '@/lib/format';

// ── Search Command Palette ──
function SearchPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (open) {
      setQuery('');
      setResults(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (query.length < 2) { setResults(null); return; }
    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.search(query);
        setResults(res);
      } catch { /* ignore */ }
      setLoading(false);
    }, 300);
    return () => clearTimeout(timeout);
  }, [query]);

  const navigate = (href: string) => { router.push(href); onClose(); };

  if (!open) return null;

  const totalResults = results ? results.transactions.length + results.cases.length + results.api_keys.length : 0;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" />
      <div className="relative w-full max-w-xl bg-white border border-border rounded-xl shadow-dropdown overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border-light">
          <svg className="w-5 h-5 text-ink-light shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search transactions, cases, API keys..."
            className="flex-1 bg-transparent text-sm text-ink placeholder-ink-light outline-none"
          />
          <kbd className="hidden sm:inline text-[10px] text-ink-light bg-bg px-1.5 py-0.5 rounded border border-border-light">ESC</kbd>
        </div>

        <div className="max-h-80 overflow-y-auto">
          {loading && <div className="p-6 text-center text-sm text-ink-muted">Searching...</div>}
          {!loading && query.length >= 2 && totalResults === 0 && (
            <div className="p-6 text-center text-sm text-ink-muted">No results for &quot;{query}&quot;</div>
          )}
          {!loading && results && totalResults > 0 && (
            <div className="p-2">
              {results.transactions.length > 0 && (
                <div className="mb-2">
                  <div className="px-3 py-1.5 text-[10px] font-semibold text-ink-muted uppercase tracking-wider">Transactions</div>
                  {results.transactions.map(tx => (
                    <button key={tx.id} onClick={() => navigate('/transactions')} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-bg transition-colors text-left">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${tx.status === 'blocked' ? 'bg-red-500' : tx.status === 'approved' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-ink truncate">{formatCurrency(tx.amount, tx.currency)} — {tx.sender} → {tx.receiver}</div>
                        <div className="text-[10px] text-ink-light">{timeAgo(tx.created_at)}</div>
                      </div>
                      <span className="text-xs text-ink-muted capitalize">{tx.status}</span>
                    </button>
                  ))}
                </div>
              )}
              {results.cases.length > 0 && (
                <div className="mb-2">
                  <div className="px-3 py-1.5 text-[10px] font-semibold text-ink-muted uppercase tracking-wider">Cases</div>
                  {results.cases.map(c => (
                    <button key={c.case_id} onClick={() => navigate('/cases')} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-bg transition-colors text-left">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${c.status === 'resolved' ? 'bg-emerald-500' : c.status === 'escalated' ? 'bg-red-500' : 'bg-blue-500'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-ink truncate">{c.case_id} — {c.reason}</div>
                        <div className="text-[10px] text-ink-light">{c.priority} priority</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {results.api_keys.length > 0 && (
                <div>
                  <div className="px-3 py-1.5 text-[10px] font-semibold text-ink-muted uppercase tracking-wider">API Keys</div>
                  {results.api_keys.map(k => (
                    <button key={k.id} onClick={() => navigate('/api-keys')} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-bg transition-colors text-left">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${k.is_active ? 'bg-emerald-500' : 'bg-gray-400'}`} />
                      <div className="text-sm text-ink">{k.name}</div>
                      <span className="text-xs text-ink-light font-mono">{k.key_prefix}••••</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {!loading && query.length < 2 && (
            <div className="p-6 text-center text-sm text-ink-muted">Type at least 2 characters to search</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Notification Dropdown ──
function NotificationDropdown({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [data, setData] = useState<NotificationListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listNotifications(15);
      setData(res);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { if (open) load(); }, [open, load]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  const handleMarkRead = async (id: string) => {
    await api.markNotificationRead(id);
    load();
  };

  const handleMarkAllRead = async () => {
    await api.markAllNotificationsRead();
    load();
  };

  if (!open) return null;

  return (
    <div ref={ref} className="absolute right-0 top-full mt-2 w-80 bg-white border border-border rounded-xl shadow-dropdown overflow-hidden z-50">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-light">
        <span className="text-sm font-semibold text-ink">Notifications</span>
        {data && data.unread_count > 0 && (
          <button onClick={handleMarkAllRead} className="text-[10px] text-accent hover:text-accent-dark font-medium">Mark all read</button>
        )}
      </div>
      <div className="max-h-72 overflow-y-auto">
        {loading ? (
          <div className="p-6 text-center text-sm text-ink-muted">Loading...</div>
        ) : !data || data.notifications.length === 0 ? (
          <div className="p-6 text-center text-sm text-ink-muted">No notifications</div>
        ) : (
          data.notifications.map(n => (
            <div key={n.id} className={`px-4 py-3 border-b border-border-light last:border-0 hover:bg-bg-alt transition-colors ${!n.is_read ? 'bg-amber-50/50' : ''}`}>
              <div className="flex items-start gap-2.5">
                <span className="text-sm mt-0.5">{TYPE_ICONS[n.type] || '🔔'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-ink">{n.title}</span>
                    {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />}
                  </div>
                  <p className="text-[11px] text-ink-muted mt-0.5 leading-relaxed">{n.message}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[10px] text-ink-light">{timeAgo(n.created_at)}</span>
                    {n.link && (
                      <Link href={n.link} className="text-[10px] text-accent hover:text-accent-dark font-medium" onClick={onClose}>View →</Link>
                    )}
                    {!n.is_read && (
                      <button onClick={() => handleMarkRead(n.id)} className="text-[10px] text-ink-light hover:text-ink-muted">Dismiss</button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const TYPE_ICONS: Record<string, string> = {
  blocked_tx: '🚫',
  new_case: '📁',
  credit_alert: '💰',
  plan_change: '📋',
  system: '🔔',
};

// ── Trial Countdown Badge ──
function TrialBadge({ expiresAt }: { expiresAt: string }) {
  const daysLeft = Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86400000));
  const isExpired = daysLeft === 0;
  const isUrgent = daysLeft <= 3;

  return (
    <Link href="/settings?tab=billing" className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
      isExpired
        ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
        : isUrgent
        ? 'bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100'
        : 'bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100'
    }`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      {isExpired ? 'Trial expired — Upgrade' : `${daysLeft} day${daysLeft === 1 ? '' : 's'} left`}
    </Link>
  );
}

// ── Main Topbar ──
export default function Topbar() {
  const { user, logout } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.listNotifications(1, true);
        setUnreadCount(res.unread_count);
      } catch { /* ignore */ }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />

      <header className="h-14 bg-white border-b border-border flex items-center justify-between px-6 sticky top-0 z-40">
        {/* Search */}
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 bg-bg rounded-lg px-3 py-2 flex-1 hover:bg-bg-alt border border-border-light hover:border-border transition-all text-left"
          >
            <svg className="w-4 h-4 text-ink-light shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <span className="text-sm text-ink-light flex-1">Search transactions, cases...</span>
            <kbd className="hidden sm:inline text-[10px] text-ink-light bg-white px-1.5 py-0.5 rounded border border-border-light">⌘K</kbd>
          </button>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Trial badge */}
          {user?.is_trial && user?.trial_expires_at && (
            <TrialBadge expiresAt={user.trial_expires_at} />
          )}

          {/* Credits */}
          <div className="hidden sm:flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
            <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a2.25 2.25 0 00-6.241-2.25A2.25 2.25 0 0012 7.5a2.25 2.25 0 00-2.759 2.25A2.25 2.25 0 003 12a2.25 2.25 0 006.241 2.25A2.25 2.25 0 0012 16.5a2.25 2.25 0 002.759-2.25A2.25 2.25 0 0021 12z" />
            </svg>
            <span className="text-sm font-semibold text-accent-dark">{formatNumber(user?.credits_remaining ?? 0)}</span>
            <span className="text-[10px] text-ink-light hidden lg:inline">{timezoneLabel(USER_TIMEZONE)}</span>
          </div>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setNotifOpen(!notifOpen)}
              className="relative p-2 text-ink-muted hover:text-ink transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-accent rounded-full text-[9px] text-white font-bold flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
            <NotificationDropdown open={notifOpen} onClose={() => setNotifOpen(false)} />
          </div>

          {/* User menu */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center text-accent text-xs font-bold">
              {user?.first_name?.charAt(0) || 'U'}
            </div>
            <div className="hidden md:block">
              <div className="text-sm font-medium text-ink">{user ? `${user.first_name} ${user.last_name}` : 'User'}</div>
              <div className="text-[10px] text-ink-muted">{user?.company || ''}</div>
            </div>
            <button
              onClick={logout}
              className="p-1.5 text-ink-light hover:text-ink transition-colors"
              title="Sign out"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
            </button>
          </div>
        </div>
      </header>
    </>
  );
}
