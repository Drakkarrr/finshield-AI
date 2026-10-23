'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import RiskScore from '@/components/RiskScore';
import { useAuth } from '@/contexts/AuthContext';
import { api, errorMessage, StatsData } from '@/lib/api';
import {
  Alert, Badge, Card, EmptyState, LoadingState, Meter, PageHeader, StatusBadge, Table, TBody, THead, Td, Th, Tr,
  buttonClasses, humanize,
} from '@/components/ui';
import { calcCredits, formatCurrency, formatNumber, formatTime, timeAgo } from '@/lib/format';

// S5.7: honest polling, not push. SWR pauses refreshInterval while the tab is hidden.
const REFRESH_MS = 15_000;

function Dashboard() {
  const { user } = useAuth();
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const poll = { refreshInterval: REFRESH_MS, onSuccess: () => setUpdatedAt(new Date()) };
  const stats = useSWR('stats', api.getStats, poll);
  const recent = useSWR('transactions:recent', () => api.listTransactions(6, 0), poll);
  const health = useSWR('health', api.health, { refreshInterval: REFRESH_MS });
  const overall = useSWR('health:overall', api.overallHealth, { refreshInterval: REFRESH_MS });

  if (stats.isLoading && !stats.data) return <LoadingState label="Loading your compliance overview…" />;

  const s = stats.data;
  const credits = calcCredits(user?.total_credits ?? 0, user?.used_credits ?? 0);
  const error = stats.error ?? recent.error;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome, ${user?.first_name || 'there'}`}
        description="Compliance overview for your organisation"
        actions={
          <p className="text-xs text-ink-muted" aria-live="polite">
            Auto-refreshes every {REFRESH_MS / 1000} s while this tab is visible
            {updatedAt && <> · Last updated <time dateTime={updatedAt.toISOString()}>{formatTime(updatedAt.toISOString())}</time></>}
          </p>
        }
      />

      {error && <Alert tone="danger" title="Could not load the overview">{errorMessage(error)}</Alert>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total screened', value: s?.total_transactions ?? 0, cls: 'text-ink' },
          { label: 'Flagged', value: s?.flagged ?? 0, cls: 'text-warning-fg' },
          { label: 'Blocked', value: s?.blocked ?? 0, cls: 'text-danger-fg' },
          { label: 'Open cases', value: s?.open_cases ?? 0, cls: 'text-info-fg' },
        ].map((kpi) => (
          <Card key={kpi.label}>
            <h2 className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-3">{kpi.label}</h2>
            <p className={`text-3xl font-bold ${kpi.cls}`}>{formatNumber(kpi.value)}</p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card as="section" aria-labelledby="results-h">
          <h2 id="results-h" className="text-sm font-semibold text-ink mb-4">Screening results</h2>
          {!s || s.total_transactions === 0 ? (
            <EmptyState
              title="No transactions screened yet."
              action={<Link href="/transactions" className={buttonClasses('primary', 'sm')}>Screen your first transaction</Link>}
            />
          ) : (
            <Breakdown stats={s} />
          )}
        </Card>

        <Card as="section" aria-labelledby="credits-h">
          <h2 id="credits-h" className="text-sm font-semibold text-ink mb-4">Credit usage</h2>
          <p className="text-3xl font-bold text-accent-fg mb-1">{formatNumber(credits.remaining)}</p>
          <p className="text-xs text-ink-muted mb-4">credits remaining</p>
          <Meter value={credits.used} max={credits.total || 1} label="Credits used" valueText={`${credits.pctUsed}% used`} />
          <p className="text-2xs text-ink-muted mt-2 mb-4">
            {formatNumber(credits.used)} of {formatNumber(credits.total)} used ({credits.pctUsed}%)
          </p>
          <Link href="/settings?tab=billing" className={buttonClasses('secondary', 'md', 'w-full')}>Billing</Link>
        </Card>

        <Card as="section" aria-labelledby="health-h">
          <h2 id="health-h" className="text-sm font-semibold text-ink mb-3">System health</h2>
          {overall.data && (
            <Alert tone={overall.data.health === 'green' ? 'success' : overall.data.health === 'yellow' ? 'warning' : 'danger'} className="mb-3">
              {overall.data.message}
            </Alert>
          )}
          {health.error ? (
            <Alert tone="danger">API unreachable: {errorMessage(health.error)}</Alert>
          ) : (
            <ul className="grid grid-cols-2 gap-2">
              {Object.entries(health.data?.services ?? {}).map(([svc, st]) => (
                <li key={svc} className="bg-bg-alt rounded-lg px-3 py-2">
                  <p className="text-2xs text-ink-muted">{humanize(svc)}</p>
                  <Badge tone={st === 'healthy' ? 'success' : 'warning'}>{humanize(st)}</Badge>
                </li>
              ))}
            </ul>
          )}
          {health.data && <p className="text-2xs text-ink-muted mt-3">API version {health.data.version}</p>}
        </Card>
      </div>

      <Card as="section" padding="none" aria-labelledby="recent-h">
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 id="recent-h" className="text-sm font-semibold text-ink">Recent transactions</h2>
          <Link href="/transactions" className="text-xs font-medium">View all</Link>
        </div>
        {!recent.data || recent.data.items.length === 0 ? (
          <EmptyState title="No transactions yet." description="Screened transactions appear here." />
        ) : (
          <Table caption="Six most recent transactions">
            <THead>
              <Th>Amount</Th><Th>Parties</Th><Th>Status</Th><Th>Risk</Th><Th>Time</Th>
            </THead>
            <TBody>
              {recent.data.items.map((tx) => (
                <Tr key={tx.id}>
                  <Td className="text-ink font-medium">{formatCurrency(tx.amount, tx.currency)}</Td>
                  <Td className="text-xs text-ink-secondary">{tx.sender} → {tx.receiver}</Td>
                  <Td><StatusBadge status={tx.status} /></Td>
                  <Td><RiskScore score={tx.risk_score} /></Td>
                  <Td className="text-xs text-ink-muted">{timeAgo(tx.created_at)}</Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function Breakdown({ stats }: { stats: StatsData }) {
  const total = stats.total_transactions;
  const rows = [
    { label: 'Approved', value: stats.approved, tone: 'success' as const },
    { label: 'Flagged', value: stats.flagged, tone: 'warning' as const },
    { label: 'Blocked', value: stats.blocked, tone: 'danger' as const },
    { label: 'In review', value: stats.in_review, tone: 'info' as const },
  ];
  return (
    <ul className="space-y-3">
      {rows.map((r) => {
        const pct = total > 0 ? Math.round((r.value / total) * 100) : 0;
        return (
          <li key={r.label}>
            <Meter value={r.value} max={total} label={r.label} tone={r.tone} showValue valueText={`${formatNumber(r.value)} (${pct}%)`} />
          </li>
        );
      })}
    </ul>
  );
}

export default function DashboardPage() {
  return (
    <PlatformLayout>
      <Dashboard />
    </PlatformLayout>
  );
}
