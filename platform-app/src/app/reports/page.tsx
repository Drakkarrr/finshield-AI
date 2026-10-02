'use client';

import React, { useState, useEffect } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { api, StatsData } from '@/lib/api';

export default function ReportsPage() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getStats()
      .then(setStats)
      .catch(e => setError(e.message || 'Failed to load report data.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PlatformLayout>
        <div className="glass p-12 text-center">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-ink-muted">Generating report...</p>
        </div>
      </PlatformLayout>
    );
  }

  const total = stats?.total_transactions ?? 0;
  const pctOf = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);

  return (
    <PlatformLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">Reports</h1>
            <p className="text-sm text-ink-muted mt-0.5">Compliance analytics across all screened transactions</p>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>
        )}

        {total === 0 ? (
          <div className="glass p-12 text-center">
            <p className="text-sm text-ink-light">No data to report yet. Screen transactions to populate this report.</p>
          </div>
        ) : (
          <>
            {/* Summary metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: 'Total Screened', value: total.toLocaleString() },
                { label: 'Avg Risk Score', value: `${((stats?.avg_risk_score ?? 0) * 100).toFixed(1)}%` },
                { label: 'Credits Used', value: (stats?.credits_used ?? 0).toLocaleString() },
                { label: 'Open Cases', value: (stats?.open_cases ?? 0).toLocaleString() },
              ].map((m) => (
                <div key={m.label} className="glass p-5">
                  <div className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-2">{m.label}</div>
                  <div className="text-2xl font-bold text-ink">{m.value}</div>
                </div>
              ))}
            </div>

            {/* Decision breakdown bars */}
            <div className="glass p-6">
              <h3 className="text-sm font-semibold text-ink mb-4">Decision Breakdown</h3>
              <div className="space-y-4">
                {[
                  { label: 'Approved', value: stats?.approved ?? 0, color: 'bg-emerald-500' },
                  { label: 'Flagged', value: stats?.flagged ?? 0, color: 'bg-amber-500' },
                  { label: 'In Review', value: stats?.in_review ?? 0, color: 'bg-blue-500' },
                  { label: 'Blocked', value: stats?.blocked ?? 0, color: 'bg-red-500' },
                ].map((row) => (
                  <div key={row.label}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm text-ink-secondary">{row.label}</span>
                      <span className="text-sm text-ink-muted font-mono">{row.value} ({pctOf(row.value)}%)</span>
                    </div>
                    <div className="w-full h-2 bg-bg rounded-full overflow-hidden">
                      <div className={`h-full ${row.color} rounded-full transition-all`} style={{ width: `${pctOf(row.value)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk distribution summary */}
            <div className="glass p-6">
              <h3 className="text-sm font-semibold text-ink mb-3">Risk Posture</h3>
              <p className="text-sm text-ink-muted leading-relaxed">
                Across {total.toLocaleString()} screened transaction{total === 1 ? '' : 's'}, the average risk score is{' '}
                <span className="text-ink font-semibold">{((stats?.avg_risk_score ?? 0) * 100).toFixed(1)}%</span>.{' '}
                {pctOf(stats?.blocked ?? 0) + pctOf(stats?.flagged ?? 0) > 20
                  ? 'A notable share of activity is being flagged or blocked — review your rule thresholds and sender population.'
                  : 'The majority of activity is low-risk and passes automated screening.'}
              </p>
            </div>
          </>
        )}
      </div>
    </PlatformLayout>
  );
}
