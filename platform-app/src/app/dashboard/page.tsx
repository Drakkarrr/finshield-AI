'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth } from '@/contexts/AuthContext';
import { api, StatsData, HealthData, TransactionListItem } from '@/lib/api';
import { formatCurrency, formatNumber, formatDateTime, timeAgo as timeAgoFmt, calcCredits } from '@/lib/format';

const STATUS_COLORS: Record<string, string> = {
  approved: 'text-emerald-600 bg-emerald-50',
  flagged: 'text-amber-600 bg-amber-50',
  blocked: 'text-red-600 bg-red-50',
  in_review: 'text-blue-600 bg-blue-50',
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<StatsData | null>(null);
  const [recent, setRecent] = useState<TransactionListItem[]>([]);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [s, txs, h] = await Promise.all([
          api.getStats(),
          api.listTransactions(6, 0),
          api.health(),
        ]);
        setStats(s);
        setRecent(txs);
        setHealth(h);
      } catch (e: any) {
        setError(e.message || 'Unable to reach the FinShield API.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <PlatformLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="w-10 h-10 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-ink-muted">Loading your compliance overview...</p>
          </div>
        </div>
      </PlatformLayout>
    );
  }

  const firstName = user?.first_name || 'there';

  return (
    <PlatformLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">Welcome, {firstName}</h1>
            <p className="text-sm text-ink-muted mt-0.5">Your real-time compliance overview</p>
          </div>
          <div className="flex items-center gap-2">
            {error ? (
              <span className="text-xs text-red-600">API offline</span>
            ) : (
              <>
                <span className={`w-2 h-2 rounded-full ${health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
                <span className="text-xs text-ink-muted">API v{health?.version || '—'}</span>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">
            {error} Make sure the backend is running on port 8091.
          </div>
        )}

        {/* KPI Cards — real data */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Screened', value: stats?.total_transactions ?? 0, color: 'text-ink' },
            { label: 'Flagged', value: stats?.flagged ?? 0, color: 'text-amber-600' },
            { label: 'Blocked', value: stats?.blocked ?? 0, color: 'text-red-600' },
            { label: 'Open Cases', value: stats?.open_cases ?? 0, color: 'text-blue-600' },
          ].map((kpi, i) => (
            <div key={kpi.label} className={`glass p-5 animate-fade-in-up animate-delay-${i + 1}`}>
              <div className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-3">{kpi.label}</div>
              <div className={`text-3xl font-bold ${kpi.color}`}>{formatNumber(kpi.value)}</div>
            </div>
          ))}
        </div>

        {/* Results breakdown + credits */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="glass p-5">
            <h3 className="text-sm font-semibold text-ink mb-4">Screening Results</h3>
            {(stats?.total_transactions ?? 0) === 0 ? (
              <EmptyState text="No transactions screened yet." cta="Screen your first transaction" href="/transactions" />
            ) : (
              <>
                <div className="flex items-center justify-center mb-4">
                  <div className="relative w-36 h-36">
                    <div
                      className="w-full h-full rounded-full"
                      style={{ background: donutGradient(stats!) }}
                    />
                    <div className="absolute inset-4 bg-bg rounded-full flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-xl font-bold text-ink">{formatNumber(stats!.total_transactions)}</div>
                        <div className="text-[10px] text-ink-muted">Total</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  {[
                    { label: 'Approved', value: stats!.approved, color: 'bg-emerald-500' },
                    { label: 'Flagged', value: stats!.flagged, color: 'bg-amber-500' },
                    { label: 'Blocked', value: stats!.blocked, color: 'bg-red-500' },
                    { label: 'In Review', value: stats!.in_review, color: 'bg-blue-500' },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`w-2.5 h-2.5 rounded-full ${item.color}`} />
                        <span className="text-xs text-ink-muted">{item.label}</span>
                      </div>
                      <span className="text-xs font-semibold text-ink-secondary">{item.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Credits card */}
          <div className="glass p-5">
            <h3 className="text-sm font-semibold text-ink mb-4">Credit Usage</h3>
            {(() => {
              const c = calcCredits(user?.total_credits ?? 0, user?.used_credits ?? 0);
              return (
                <>
                  <div className="text-3xl font-bold text-accent-dark mb-1">
                    {formatNumber(c.remaining)}
                  </div>
                  <div className="text-xs text-ink-muted mb-4">credits remaining</div>
                  <div className="w-full h-2 bg-bg rounded-full overflow-hidden mb-2">
                    <div
                      className="h-full bg-accent rounded-full transition-all duration-500"
                      style={{ width: `${c.pctUsed}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-ink-light mb-4">
                    {formatNumber(c.used)} of {formatNumber(c.total)} used ({c.pctUsed}%)
                  </div>
                </>
              );
            })()}
            <Link href="/settings?tab=billing" className="block text-center bg-accent/10 hover:bg-accent/20 text-accent-dark text-sm font-semibold py-2.5 rounded-xl transition-all">
              Manage billing
            </Link>
          </div>

          {/* System health */}
          <div className="glass p-5">
            <h3 className="text-sm font-semibold text-ink mb-3">System Health</h3>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(health?.services ?? { database: 'unknown' }).map(([svc, st]) => (
                <div key={svc} className="flex items-center gap-2 bg-bg-alt rounded-lg px-3 py-2">
                  <span className={`w-2 h-2 rounded-full ${st === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                  <div className="truncate">
                    <div className="text-[10px] text-ink-muted capitalize">{svc.replace(/_/g, ' ')}</div>
                    <div className="text-[10px] text-ink-light">{st}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Transactions */}
        <div className="glass p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-ink">Recent Transactions</h3>
            <Link href="/transactions" className="text-xs text-accent-dark hover:text-accent-dark-dark transition-colors">View all</Link>
          </div>
          {recent.length === 0 ? (
            <EmptyState text="No transactions yet. Screened transactions will appear here." cta="Screen a transaction" href="/transactions" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink-light border-b border-border-light">
                    <th className="pb-2 font-medium">Amount</th>
                    <th className="pb-2 font-medium">Parties</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Risk</th>
                    <th className="pb-2 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((tx) => (
                    <tr key={tx.id} className="border-b border-border-light hover:bg-bg-alt transition-colors">
                      <td className="py-3 text-ink font-medium">{formatCurrency(tx.amount, tx.currency)}</td>
                      <td className="py-3">
                        <div className="text-xs text-ink-secondary">{tx.sender} → {tx.receiver}</div>
                      </td>
                      <td className="py-3">
                        <span className={`status-badge status-${tx.status === 'in_review' ? 'review' : tx.status}`}>
                          <span className="status-dot" />
                          {tx.status === 'in_review' ? 'In Review' : tx.status.charAt(0).toUpperCase() + tx.status.slice(1)}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className={`text-xs font-mono ${tx.risk_score > 0.7 ? 'text-red-600' : tx.risk_score > 0.4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                          {(tx.risk_score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-3 text-xs text-ink-light">{timeAgoFmt(tx.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </PlatformLayout>
  );
}

function donutGradient(s: StatsData): string {
  const total = s.total_transactions || 1;
  const seg = (n: number) => (n / total) * 360;
  const approved = seg(s.approved);
  const flagged = approved + seg(s.flagged);
  const blocked = flagged + seg(s.blocked);
  return `conic-gradient(
    #10B981 0deg ${approved}deg,
    #F59E0B ${approved}deg ${flagged}deg,
    #EF4444 ${flagged}deg ${blocked}deg,
    #3B82F6 ${blocked}deg 360deg
  )`;
}

function pctUsed(stats: StatsData | null, user: any): number {
  const c = calcCredits(user?.total_credits ?? 0, user?.used_credits ?? 0);
  return c.pctUsed;
}

function EmptyState({ text, cta, href }: { text: string; cta: string; href: string }) {
  return (
    <div className="text-center py-8">
      <p className="text-sm text-ink-light mb-4">{text}</p>
      <Link href={href} className="inline-block bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-4 py-2 rounded-xl transition-all">
        {cta}
      </Link>
    </div>
  );
}
