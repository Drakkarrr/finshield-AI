'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import RiskScore from '@/components/RiskScore';
import { useAuth, useCan } from '@/contexts/AuthContext';
import { api, errorMessage, ScreeningResult, TransactionDetail, TransactionRequest } from '@/lib/api';
import {
  Alert, Badge, Button, Card, EmptyState, FilterChips, InfoRow, Input, LoadingState, Meter, Modal, PageHeader,
  Pagination, Select, StatusBadge, Table, TBody, THead, Td, Th, Tr, humanize,
} from '@/components/ui';
import { countryName, formatCurrency, formatDate, formatDateTime, formatPercent, timeAgo } from '@/lib/format';

const PAGE_SIZES = [25, 50, 100, 250];

const STATUS_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'approved', label: 'Approved' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'in_review', label: 'In review' },
] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number]['value'];

const CURRENCIES = ['USD', 'EUR', 'GBP', 'PHP', 'SGD', 'JPY', 'CNY', 'HKD'].map((c) => ({ value: c, label: c }));
const TX_TYPES = [
  { value: 'wire', label: 'Wire transfer' },
  { value: 'ach', label: 'ACH transfer' },
  { value: 'international', label: 'International wire' },
  { value: 'crypto', label: 'Cryptocurrency' },
  { value: 'p2p', label: 'Peer-to-peer' },
  { value: 'card', label: 'Card payment' },
];

function Transactions() {
  const can = useCan();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [showScreen, setShowScreen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [showExport, setShowExport] = useState(false);
  const [actionError, setActionError] = useState('');

  const list = useSWR(['transactions', page, pageSize], () => api.listTransactions(pageSize, page * pageSize));
  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const filtered = filter === 'all' ? items : items.filter((t) => t.status === filter);
  const canDelete = can(['DELETE', '/api/v1/transactions/{tx_id}']);

  const handleDelete = async (txId: string) => {
    if (!window.confirm('This will pseudonymise the transaction (remove PII) if outside the retention window. Continue?')) return;
    try {
      await api.deleteTransaction(txId);
      setDetailId(null);
      await list.mutate();
    } catch (e) {
      setActionError(errorMessage(e, 'Failed to delete transaction.'));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions"
        description="Screen and monitor transaction compliance"
        actions={
          <>
            <Button variant="secondary" onClick={() => setShowExport(true)} disabled={total === 0}>Export CSV</Button>
            <Button onClick={() => setShowScreen(!showScreen)} aria-expanded={showScreen} aria-controls="screen-form">
              {showScreen ? 'Close screening form' : 'Screen transaction'}
            </Button>
          </>
        }
      />

      {actionError && <Alert tone="danger" onDismiss={() => setActionError('')}>{actionError}</Alert>}
      {showScreen && <ScreenForm onScreened={() => { setPage(0); list.mutate(); }} />}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <FilterChips label="Filter the transactions on this page by status" options={STATUS_FILTERS} value={filter} onChange={setFilter} />
        <Select
          label="Rows per page"
          className="w-36"
          value={String(pageSize)}
          onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
          options={PAGE_SIZES.map((n) => ({ value: String(n), label: String(n) }))}
        />
      </div>

      <Card padding="none">
        {list.isLoading && !list.data ? (
          <LoadingState label="Loading transactions…" />
        ) : list.error ? (
          <div className="p-5"><Alert tone="danger" title="Could not load transactions">{errorMessage(list.error)}</Alert></div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title={total === 0 ? 'No transactions screened yet.' : 'No transactions on this page match the filter.'}
            description={total === 0 ? 'Use “Screen transaction” to run your first compliance check.' : undefined}
          />
        ) : (
          <Table caption={`Transactions, page ${page + 1}`}>
            <THead>
              <Th>Amount</Th><Th>Parties</Th><Th>Status</Th><Th>Risk score</Th><Th>Tier</Th><Th>Time</Th>
              <Th align="right">Actions</Th>
            </THead>
            <TBody>
              {filtered.map((tx) => (
                <Tr key={tx.id}>
                  <Td className="text-ink font-medium">{formatCurrency(tx.amount, tx.currency)}</Td>
                  <Td>
                    <span className="block text-xs text-ink-secondary">{tx.sender}</span>
                    <span className="block text-2xs text-ink-muted">→ {tx.receiver}</span>
                  </Td>
                  <Td><StatusBadge status={tx.status} /></Td>
                  <Td><RiskScore score={tx.risk_score} digits={1} /></Td>
                  <Td className="text-xs text-ink-muted">{humanize(tx.credit_tier)}</Td>
                  <Td className="text-xs text-ink-muted"><time dateTime={tx.created_at} title={formatDateTime(tx.created_at)}>{timeAgo(tx.created_at)}</time></Td>
                  <Td align="right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setDetailId(tx.id)} aria-label={`View detail of transaction ${tx.id}`}>
                        Detail
                      </Button>
                      {canDelete && (
                        <Button variant="danger" size="sm" onClick={() => handleDelete(tx.id)} aria-label={`Delete transaction ${tx.id}`}>
                          Delete
                        </Button>
                      )}
                    </div>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
        {total > 0 && (
          <Pagination label="Transactions pages" page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        )}
      </Card>

      {detailId && (
        <DetailModal txId={detailId} onClose={() => setDetailId(null)} onDelete={canDelete ? handleDelete : undefined} />
      )}
      <ExportModal open={showExport} onClose={() => setShowExport(false)} />
    </div>
  );
}

// ── Screening form ──
function ScreenForm({ onScreened }: { onScreened: () => void }) {
  const { refreshUser } = useAuth();
  const [form, setForm] = useState({
    sender_name: '', receiver_name: '', amount: '', currency: 'USD',
    transaction_type: 'wire' as TransactionRequest['transaction_type'], destination_country: '',
  });
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: k === 'destination_country' ? e.target.value.toUpperCase() : e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.screenTransaction({
        sender_name: form.sender_name,
        receiver_name: form.receiver_name,
        amount: parseFloat(form.amount),
        currency: form.currency,
        transaction_type: form.transaction_type,
        destination_country: form.destination_country || undefined,
      });
      if (!res.success || !res.data) throw new Error(res.error || 'Screening failed.');
      setResult(res.data);
      onScreened();
      refreshUser();
    } catch (err) {
      setError(errorMessage(err, 'Screening failed.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card as="section" padding="lg" id="screen-form" aria-labelledby="screen-h">
      <h2 id="screen-h" className="text-sm font-semibold text-ink mb-4">Screen a transaction</h2>
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Input label="Sender name" placeholder="e.g. Acme Corp" value={form.sender_name} onChange={set('sender_name')} required />
        <Input label="Receiver name" placeholder="e.g. John Doe" value={form.receiver_name} onChange={set('receiver_name')} required />
        <Input label="Amount" type="number" inputMode="decimal" value={form.amount} onChange={set('amount')} required min="0.01" step="0.01" />
        <Select label="Currency" value={form.currency} onChange={set('currency')} options={CURRENCIES} />
        <Select label="Transaction type" value={form.transaction_type} onChange={set('transaction_type')} options={TX_TYPES} />
        <Input label="Destination country" helpText="ISO 3166 alpha-2, e.g. US, PH, SG" value={form.destination_country} onChange={set('destination_country')} maxLength={2} />
        <div className="md:col-span-3 flex justify-end">
          <Button type="submit" loading={loading}>{loading ? 'Screening…' : 'Screen transaction'}</Button>
        </div>
      </form>
      {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
      {result && (
        <Alert tone={result.status === 'approved' ? 'success' : result.status === 'blocked' ? 'danger' : 'warning'} className="mt-4" title={`Result: ${humanize(result.status)}`}>
          <p>Risk {formatPercent(result.risk_score, 1)} · Tier {humanize(result.credit_tier)} · {result.credits_consumed} credits · {result.total_latency_ms} ms</p>
          <p className="text-xs mt-1">Pipeline: {result.pipeline_stages.map(humanize).join(' → ')}</p>
        </Alert>
      )}
    </Card>
  );
}

// ── Detail ──
function DetailModal({ txId, onClose, onDelete }: { txId: string; onClose: () => void; onDelete?: (id: string) => void }) {
  const { data: tx, error, isLoading } = useSWR(['transaction', txId], () => api.getTransaction(txId));
  return (
    <Modal
      open
      onClose={onClose}
      title="Transaction detail"
      description={txId}
      size="2xl"
      footer={
        <>
          {onDelete && <Button variant="danger" onClick={() => onDelete(txId)}>Delete transaction</Button>}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </>
      }
    >
      {isLoading ? <LoadingState label="Loading transaction…" /> : error ? (
        <Alert tone="danger">{errorMessage(error)}</Alert>
      ) : tx && <DetailBody tx={tx} />}
    </Modal>
  );
}

function DetailBody({ tx }: { tx: TransactionDetail }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={tx.status} />
        <RiskScore score={tx.risk_score} digits={1} />
        {tx.degraded && <Badge tone="warning">Degraded mode — routed to review</Badge>}
        {tx.model_version && <Badge tone="neutral">Model {tx.model_version}</Badge>}
      </div>

      <dl className="grid grid-cols-2 gap-4">
        <InfoRow label="Amount" value={formatCurrency(tx.amount, tx.currency)} />
        <InfoRow label="Type" value={humanize(tx.transaction_type)} />
        <InfoRow label="Sender" value={tx.sender_name} />
        <InfoRow label="Receiver" value={tx.receiver_name} />
        <InfoRow label="Country" value={tx.destination_country ? `${tx.destination_country} — ${countryName(tx.destination_country)}` : '—'} />
        <InfoRow label="Credit tier" value={humanize(tx.credit_tier)} />
        <InfoRow label="Credits used" value={String(tx.credits_consumed)} />
        {tx.total_latency_ms != null && <InfoRow label="Total latency" value={`${tx.total_latency_ms.toFixed(2)} ms`} />}
        <InfoRow label="Created" value={formatDateTime(tx.created_at)} full />
      </dl>

      {tx.reasons.length > 0 && (
        <section aria-labelledby="reasons-h">
          <h3 id="reasons-h" className="text-sm font-semibold text-ink mb-2">Why this decision</h3>
          <Table caption="Decision reasons">
            <THead><Th>Source</Th><Th>Feature</Th><Th>Detail</Th><Th align="right">Contribution</Th></THead>
            <TBody>
              {tx.reasons.map((r, i) => (
                <Tr key={i}>
                  <Td className="text-xs">{humanize(r.source)}</Td>
                  <Td className="text-xs font-mono">{r.rule_id ? `${r.rule_id} · ` : ''}{r.feature}</Td>
                  <Td className="text-xs text-ink-secondary">{r.detail || (r.value != null ? String(r.value) : '—')}</Td>
                  <Td align="right" className="text-xs font-mono">{r.contribution.toFixed(3)}</Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        </section>
      )}

      {(tx.ml_classification || tx.behavioral_score != null) && (
        <section aria-labelledby="ml-h" className="grid grid-cols-2 gap-3">
          <h3 id="ml-h" className="sr-only">Model and behavioral scores</h3>
          {tx.ml_classification && (
            <div className="rounded-lg border border-border-light p-3">
              <p className="text-2xs text-ink-muted uppercase tracking-wider mb-1">Model classification</p>
              <p className="text-sm font-semibold text-ink">{humanize(tx.ml_classification)}</p>
              {tx.ml_confidence != null && (
                <Meter className="mt-2" value={tx.ml_confidence * 100} label="Confidence" showValue valueText={formatPercent(tx.ml_confidence, 1)} />
              )}
            </div>
          )}
          {tx.behavioral_score != null && (
            <div className="rounded-lg border border-border-light p-3">
              <p className="text-2xs text-ink-muted uppercase tracking-wider mb-1">Behavioral score</p>
              <p className="text-sm font-semibold text-ink">{tx.behavioral_score.toFixed(3)}</p>
              {(() => {
                const z = Math.abs(tx.behavioral_score);
                const level = z > 3 ? 'High' : z > 2 ? 'Medium' : 'Low';
                return (
                  <Meter
                    className="mt-2"
                    value={Math.min(z * 20, 100)}
                    label="Anomaly level"
                    tone={z > 3 ? 'danger' : z > 2 ? 'warning' : 'success'}
                    showValue
                    valueText={level}
                  />
                );
              })()}
            </div>
          )}
        </section>
      )}

      {tx.account_id && <BaselinePanel accountId={tx.account_id} />}

      <section aria-labelledby="rules-h">
        <h3 id="rules-h" className="text-sm font-semibold text-ink mb-2">Rule evaluation</h3>
        {tx.rule_results.length === 0 ? (
          <p className="text-xs text-ink-muted">No rule results recorded for this transaction.</p>
        ) : (
          <ul className="space-y-2">
            {tx.rule_results.map((r, i) => (
              <li key={i} className={`rounded-lg border p-3 ${r.triggered ? 'border-danger-light bg-danger-bg' : 'border-border-light bg-bg-alt'}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-ink">{r.rule_id} — {r.rule_name}</span>
                  <span className="flex items-center gap-2">
                    <Badge tone="neutral">{humanize(r.rule_type)}</Badge>
                    <Badge tone={r.triggered ? 'danger' : 'success'}>{r.triggered ? 'Triggered' : 'Passed'}</Badge>
                  </span>
                </div>
                {r.triggered && r.detail && <p className="text-2xs text-ink-secondary mt-1">{r.detail}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {tx.pipeline_stages.length > 0 && (
        <section aria-labelledby="pipeline-h">
          <h3 id="pipeline-h" className="text-sm font-semibold text-ink mb-2">Processing pipeline ({tx.pipeline_stages.length} stages)</h3>
          <ol className="flex flex-wrap gap-2">
            {tx.pipeline_stages.map((stage, i) => (
              <li key={i} className="text-xs text-ink-secondary bg-bg-alt px-2 py-1 rounded-md border border-border-light">
                {i + 1}. {humanize(stage)}
              </li>
            ))}
          </ol>
        </section>
      )}

      {tx.rag_context && (tx.rag_context.sanctions_matches?.length || tx.rag_context.policies?.length || tx.rag_context.similar_precedents?.length) ? (
        <section aria-labelledby="rag-h" className="space-y-3">
          <h3 id="rag-h" className="text-sm font-semibold text-ink">Retrieved context</h3>
          {tx.rag_context.sanctions_matches?.length > 0 && (
            <div>
              <h4 className="text-2xs font-semibold uppercase tracking-wider text-danger-fg mb-1">Sanctions matches</h4>
              <ul className="space-y-1">
                {tx.rag_context.sanctions_matches.map((m, i) => (
                  <li key={i} className="flex justify-between text-xs bg-danger-bg border border-danger-light rounded-md px-2.5 py-1.5">
                    <span className="font-medium text-ink">{m.name}</span>
                    <span className="text-danger-fg font-semibold">{formatPercent(m.similarity_score ?? 0)} · {m.program}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {tx.rag_context.policies?.length > 0 && (
            <div>
              <h4 className="text-2xs font-semibold uppercase tracking-wider text-ink-muted mb-1">Relevant policies</h4>
              <ul className="space-y-1">
                {tx.rag_context.policies.map((p, i) => (
                  <li key={i} className="flex justify-between text-xs border border-border-light rounded-md px-2.5 py-1.5">
                    <span className="text-ink">{p.title}</span>
                    <span className="text-ink-muted">{formatPercent(p.score ?? 0)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {tx.rag_context.similar_precedents?.length > 0 && (
            <div>
              <h4 className="text-2xs font-semibold uppercase tracking-wider text-ink-muted mb-1">Similar precedents</h4>
              <ul className="space-y-1">
                {tx.rag_context.similar_precedents.map((pr, i) => (
                  <li key={i} className="flex justify-between gap-3 text-xs border border-border-light rounded-md px-2.5 py-1.5">
                    <span className="text-ink truncate">{pr.case_summary}</span>
                    {pr.decision && <StatusBadge status={pr.decision} />}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}

function BaselinePanel({ accountId }: { accountId: string }) {
  const { data, error } = useSWR(['baseline', accountId], () => api.behavioralBaseline(accountId));
  if (error) return null;
  const b = data?.baseline;
  return (
    <section aria-labelledby="baseline-h" className="rounded-lg border border-border-light p-3">
      <h3 id="baseline-h" className="text-sm font-semibold text-ink mb-2">Behavioral baseline · <span className="font-mono text-xs">{accountId}</span></h3>
      {!data ? <p className="text-xs text-ink-muted">Loading baseline…</p> : !b ? (
        <p className="text-xs text-ink-muted">No baseline computed for this account yet.</p>
      ) : (
        <dl className="grid grid-cols-2 gap-3">
          <InfoRow label="Average amount" value={formatCurrency(b.avg_amount)} />
          <InfoRow label="Std. deviation" value={formatCurrency(b.std_dev_amount)} />
          <InfoRow label="Range" value={`${formatCurrency(b.min_amount)} – ${formatCurrency(b.max_amount)}`} />
          <InfoRow label="History" value={`${b.total_transactions} transactions · ${b.history_days} days${b.is_cold_start ? ' (cold start)' : ''}`} />
          {b.typical_countries && b.typical_countries.length > 0 && <InfoRow label="Typical countries" value={b.typical_countries.join(', ')} full />}
          <InfoRow label="Computed" value={formatDateTime(b.last_computed_at)} full />
        </dl>
      )}
    </section>
  );
}

// ── Export ──
function ExportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Export transactions"
      description="Download as CSV. Leave the dates empty to export everything."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => { window.open(api.exportTransactionsUrl(start || undefined, end || undefined), '_blank'); onClose(); }}>
            Download CSV
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label="Start date" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input label="End date" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        {(start || end) && (
          <p className="text-xs text-ink-secondary">
            {start && end ? `From ${formatDate(start)} to ${formatDate(end)}` : start ? `From ${formatDate(start)} onwards` : `Up to ${formatDate(end)}`}
          </p>
        )}
      </div>
    </Modal>
  );
}

export default function TransactionsPage() {
  return (
    <PlatformLayout>
      <Transactions />
    </PlatformLayout>
  );
}
