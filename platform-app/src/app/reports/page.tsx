'use client';

import React from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { api, errorMessage } from '@/lib/api';
import { Alert, Card, EmptyState, LoadingState, Meter, PageHeader } from '@/components/ui';
import { formatNumber, formatPercent } from '@/lib/format';

function Reports() {
  const { data: stats, error, isLoading } = useSWR('stats', api.getStats);

  if (isLoading && !stats) return <LoadingState label="Generating report…" />;
  const total = stats?.total_transactions ?? 0;
  const pctOf = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Compliance analytics across all screened transactions" />
      {error && <Alert tone="danger" title="Could not load report data">{errorMessage(error)}</Alert>}

      {total === 0 ? (
        <Card><EmptyState title="No data to report yet." description="Screen transactions to populate this report." /></Card>
      ) : stats && (
        <>
          <dl className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Total screened', value: formatNumber(total) },
              { label: 'Average risk score', value: formatPercent(stats.avg_risk_score, 1) },
              { label: 'Credits used', value: formatNumber(stats.credits_used) },
              { label: 'Open cases', value: formatNumber(stats.open_cases) },
            ].map((m) => (
              <Card key={m.label}>
                <dt className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-2">{m.label}</dt>
                <dd className="text-2xl font-bold text-ink">{m.value}</dd>
              </Card>
            ))}
          </dl>

          <Card as="section" padding="lg" aria-labelledby="breakdown-h">
            <h2 id="breakdown-h" className="text-sm font-semibold text-ink mb-4">Decision breakdown</h2>
            <ul className="space-y-4">
              {[
                { label: 'Approved', value: stats.approved, tone: 'success' as const },
                { label: 'Flagged', value: stats.flagged, tone: 'warning' as const },
                { label: 'In review', value: stats.in_review, tone: 'info' as const },
                { label: 'Blocked', value: stats.blocked, tone: 'danger' as const },
              ].map((row) => (
                <li key={row.label}>
                  <Meter value={row.value} max={total} label={row.label} tone={row.tone} showValue valueText={`${formatNumber(row.value)} (${pctOf(row.value)}%)`} />
                </li>
              ))}
            </ul>
          </Card>

          <Card as="section" padding="lg" aria-labelledby="posture-h">
            <h2 id="posture-h" className="text-sm font-semibold text-ink mb-3">Risk posture</h2>
            <p className="text-sm text-ink-secondary leading-relaxed">
              Across {formatNumber(total)} screened transaction{total === 1 ? '' : 's'}, the average risk score is{' '}
              <strong className="text-ink">{formatPercent(stats.avg_risk_score, 1)}</strong>.{' '}
              {pctOf(stats.blocked) + pctOf(stats.flagged) > 20
                ? 'A notable share of activity is flagged or blocked — review rule thresholds and the sender population.'
                : 'Most activity is low-risk and passes automated screening.'}
            </p>
          </Card>
        </>
      )}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <PlatformLayout>
      <Reports />
    </PlatformLayout>
  );
}
