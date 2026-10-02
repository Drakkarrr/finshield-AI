'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { api, ScreeningResult, TransactionListItem, TransactionDetail, RuleResult } from '@/lib/api';
import { formatCurrency, formatNumber, formatDateTime, formatDate, timeAgo, countryName } from '@/lib/format';

const STATUS_OPTIONS = ['all', 'approved', 'flagged', 'blocked', 'in_review'] as const;

const RULE_TYPE_STYLES: Record<string, string> = {
  sanctions: 'bg-red-50 text-red-700 border-red-200',
  pep: 'bg-orange-50 text-orange-700 border-orange-200',
  threshold: 'bg-amber-50 text-amber-700 border-amber-200',
  geography: 'bg-blue-50 text-blue-700 border-blue-200',
};

export default function TransactionsPage() {
  const [txs, setTxs] = useState<TransactionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [screening, setScreening] = useState<ScreeningResult | null>(null);
  const [screenLoading, setScreenLoading] = useState(false);
  const [showScreen, setShowScreen] = useState(false);
  const [error, setError] = useState('');
  const [selectedTx, setSelectedTx] = useState<TransactionDetail | null>(null);
  const [txDetailLoading, setTxDetailLoading] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');
  const [form, setForm] = useState({
    sender_name: '', receiver_name: '', amount: '', currency: 'USD',
    transaction_type: 'wire' as const, destination_country: '',
  });

  const loadTxs = useCallback(async () => {
    try {
      const data = await api.listTransactions(100, 0);
      setTxs(data);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Unable to load transactions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTxs(); }, [loadTxs]);

  const filtered = filter === 'all' ? txs : txs.filter(t => t.status === filter);

  const handleScreen = async (e: React.FormEvent) => {
    e.preventDefault();
    setScreenLoading(true);
    setError('');
    try {
      const res = await api.screenTransaction({
        sender_name: form.sender_name,
        receiver_name: form.receiver_name,
        amount: parseFloat(form.amount),
        currency: form.currency,
        transaction_type: form.transaction_type as 'wire',
        destination_country: form.destination_country || undefined,
      });
      setScreening(res.data);
      await loadTxs();
    } catch (e: any) {
      setError(e.message || 'Screening failed.');
    } finally {
      setScreenLoading(false);
    }
  };

  const handleViewDetail = async (txId: string) => {
    setTxDetailLoading(true);
    setSelectedTx(null);
    try {
      const detail = await api.getTransaction(txId);
      setSelectedTx(detail);
    } catch {
      setError('Failed to load transaction detail.');
    } finally {
      setTxDetailLoading(false);
    }
  };

  const handleDelete = async (txId: string) => {
    if (!confirm('Delete this transaction and its associated cases? This cannot be undone.')) return;
    try {
      await api.deleteTransaction(txId);
      setTxs(txs.filter(t => t.id !== txId));
      if (selectedTx?.id === txId) setSelectedTx(null);
    } catch (e: any) {
      setError(e.message || 'Failed to delete transaction.');
    }
  };

  const handleExport = () => {
    window.open(api.exportTransactions(exportStartDate || undefined, exportEndDate || undefined), '_blank');
    setShowExportModal(false);
  };

  return (
    <PlatformLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">Transactions</h1>
            <p className="text-sm text-ink-muted mt-0.5">Screen and monitor transaction compliance</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowExportModal(true)}
              disabled={txs.length === 0}
              className="bg-bg hover:bg-bg-alt border border-border text-ink-secondary text-sm font-medium px-4 py-2.5 rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title="Export as CSV"
            >
              <svg className="w-4 h-4 inline mr-1.5 -mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Export Report
            </button>
            <button
              onClick={() => setShowScreen(!showScreen)}
              className="bg-accent hover:bg-accent-dark text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition-all"
            >
              {showScreen ? 'Close' : '+ Screen New'}
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>
        )}

        {/* Screen New Transaction */}
        {showScreen && (
          <div className="glass p-6 animate-fade-in-up">
            <h3 className="text-sm font-semibold text-ink mb-4">Screen Transaction</h3>
            <form onSubmit={handleScreen} className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="sender_name" className="block text-xs font-medium text-ink-muted mb-1">Sender Name</label>
                <input id="sender_name" placeholder="e.g. Acme Corp" value={form.sender_name} onChange={(e) => setForm({ ...form, sender_name: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" required aria-required="true" />
              </div>
              <div>
                <label htmlFor="receiver_name" className="block text-xs font-medium text-ink-muted mb-1">Receiver Name</label>
                <input id="receiver_name" placeholder="e.g. John Doe" value={form.receiver_name} onChange={(e) => setForm({ ...form, receiver_name: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" required aria-required="true" />
              </div>
              <div>
                <label htmlFor="amount" className="block text-xs font-medium text-ink-muted mb-1">Amount</label>
                <input id="amount" type="number" placeholder="0.00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" required min="0.01" step="0.01" aria-required="true" />
              </div>
              <div>
                <label htmlFor="currency" className="block text-xs font-medium text-ink-muted mb-1">Currency</label>
                <select id="currency" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink">
                  <option value="USD">USD — US Dollar</option>
                  <option value="EUR">EUR — Euro</option>
                  <option value="GBP">GBP — British Pound</option>
                  <option value="PHP">PHP — Philippine Peso</option>
                  <option value="SGD">SGD — Singapore Dollar</option>
                  <option value="JPY">JPY — Japanese Yen</option>
                  <option value="CNY">CNY — Chinese Yuan</option>
                  <option value="HKD">HKD — Hong Kong Dollar</option>
                </select>
              </div>
              <div>
                <label htmlFor="tx_type" className="block text-xs font-medium text-ink-muted mb-1">Transaction Type</label>
                <select id="tx_type" value={form.transaction_type} onChange={(e) => setForm({ ...form, transaction_type: e.target.value as 'wire' })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink">
                  <option value="wire">Wire Transfer</option>
                  <option value="ach">ACH Transfer</option>
                  <option value="international">International Wire</option>
                  <option value="crypto">Cryptocurrency</option>
                  <option value="p2p">Peer-to-Peer</option>
                  <option value="card">Card Payment</option>
                </select>
              </div>
              <div>
                <label htmlFor="country" className="block text-xs font-medium text-ink-muted mb-1">Destination Country</label>
                <input id="country" placeholder="e.g. US, PH, SG" value={form.destination_country} onChange={(e) => setForm({ ...form, destination_country: e.target.value.toUpperCase() })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" maxLength={2} />
              </div>
              <div className="md:col-span-3 flex justify-end">
                <button type="submit" disabled={screenLoading} className="bg-accent hover:bg-accent-dark text-white font-semibold px-6 py-2.5 rounded-xl transition-all disabled:opacity-50">
                  {screenLoading ? 'Screening...' : 'Screen Transaction'}
                </button>
              </div>
            </form>
            {screening && (
              <div className={`mt-4 p-4 rounded-xl border ${screening.status === 'approved' ? 'bg-emerald-50 border-emerald-200' : screening.status === 'blocked' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-ink">Result: {screening.status.toUpperCase()}</span>
                  <span className="text-xs text-ink-muted">Risk: {(screening.risk_score * 100).toFixed(1)}%</span>
                </div>
                <div className="text-xs text-ink-muted">
                  Tier: {screening.credit_tier} | Credits: {screening.credits_consumed} | Latency: {screening.total_latency_ms}ms | Pipeline: {screening.pipeline_stages.join(' → ')}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-2">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === s ? 'bg-accent/10 text-accent-dark' : 'text-ink-muted hover:bg-bg'
              }`}
            >
              {s === 'all' ? `All (${txs.length})` : s === 'in_review' ? 'In Review' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="glass overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-ink-muted">Loading transactions...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-sm text-ink-light">
                {txs.length === 0 ? 'No transactions screened yet. Use "Screen New" to run your first compliance check.' : 'No transactions match this filter.'}
              </p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-light border-b border-border-light">
                  <th className="px-5 py-3 font-medium">Amount</th>
                  <th className="px-5 py-3 font-medium">Parties</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Risk Score</th>
                  <th className="px-5 py-3 font-medium">Tier</th>
                  <th className="px-5 py-3 font-medium">Time</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((tx) => (
                  <tr key={tx.id} className="border-b border-border-light hover:bg-bg-alt transition-colors">
                    <td className="px-5 py-3.5 text-ink font-medium">{formatCurrency(tx.amount, tx.currency)}</td>
                    <td className="px-5 py-3.5">
                      <div className="text-xs text-ink-secondary">{tx.sender}</div>
                      <div className="text-[10px] text-ink-light">→ {tx.receiver}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`status-badge status-${tx.status === 'in_review' ? 'review' : tx.status}`}>
                        <span className="status-dot" />
                        {tx.status === 'in_review' ? 'In Review' : tx.status.charAt(0).toUpperCase() + tx.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`text-xs font-mono font-semibold ${tx.risk_score > 0.7 ? 'text-red-600' : tx.risk_score > 0.4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {(tx.risk_score * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-ink-muted">{tx.credit_tier.replace('_', '-')}</td>
                    <td className="px-5 py-3.5 text-xs text-ink-light" title={formatDateTime(tx.created_at)}>{timeAgo(tx.created_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleViewDetail(tx.id)}
                          className="text-xs text-accent-dark hover:text-accent px-2 py-1 rounded bg-accent/5 hover:bg-accent/10 transition-colors"
                          title="View detail & rule hits"
                        >
                          Detail
                        </button>
                        <button
                          onClick={() => handleDelete(tx.id)}
                          className="text-xs text-red-600 hover:text-red-700 px-2 py-1 rounded bg-red-50 hover:bg-red-100 transition-colors"
                          title="Delete transaction"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Transaction Detail Modal */}
        {selectedTx && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={() => setSelectedTx(null)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative w-full max-w-2xl bg-white border border-border rounded-2xl shadow-2xl max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="p-6 space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-ink">Transaction Detail</h3>
                    <p className="text-xs text-ink-muted font-mono mt-0.5">{selectedTx.id}</p>
                  </div>
                  <span className={`status-badge status-${selectedTx.status === 'in_review' ? 'review' : selectedTx.status}`}>
                    <span className="status-dot" />
                    {selectedTx.status === 'in_review' ? 'In Review' : selectedTx.status.charAt(0).toUpperCase() + selectedTx.status.slice(1)}
                  </span>
                </div>

                {/* Transaction Info Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <InfoRow label="Amount" value={formatCurrency(selectedTx.amount, selectedTx.currency)} />
                  <InfoRow label="Type" value={selectedTx.transaction_type} />
                  <InfoRow label="Sender" value={selectedTx.sender_name} />
                  <InfoRow label="Receiver" value={selectedTx.receiver_name} />
                  <InfoRow label="Country" value={selectedTx.destination_country ? `${selectedTx.destination_country} — ${countryName(selectedTx.destination_country)}` : '—'} />
                  <InfoRow label="Risk Score" value={`${(selectedTx.risk_score * 100).toFixed(1)}%`} />
                  <InfoRow label="Credit Tier" value={selectedTx.credit_tier.replace('_', '-')} />
                  <InfoRow label="Credits Used" value={String(selectedTx.credits_consumed)} />
                  {selectedTx.total_latency_ms != null && (
                    <InfoRow label="Total Latency" value={`${selectedTx.total_latency_ms.toFixed(2)}ms`} />
                  )}
                  <InfoRow label="Created" value={formatDateTime(selectedTx.created_at)} full />
                </div>

                {/* ML & Behavioral Scores */}
                {(selectedTx.ml_classification || selectedTx.behavioral_score != null) && (
                  <div className="rounded-xl border border-border-light bg-gradient-to-br from-purple-50/50 to-blue-50/50 p-4">
                    <h4 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      ML & Behavioral Analysis
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      {selectedTx.ml_classification && (
                        <div className="bg-white/60 rounded-lg p-3 border border-purple-100">
                          <div className="text-[10px] text-ink-muted uppercase tracking-wider mb-1">ML Classification</div>
                          <div className="text-sm font-semibold text-ink capitalize">{selectedTx.ml_classification.replace('_', ' ')}</div>
                          {selectedTx.ml_confidence != null && (
                            <div className="mt-2">
                              <div className="flex items-center justify-between text-[10px] text-ink-muted mb-1">
                                <span>Confidence</span>
                                <span className="font-semibold">{(selectedTx.ml_confidence * 100).toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-1.5">
                                <div 
                                  className="h-1.5 rounded-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all"
                                  style={{ width: `${selectedTx.ml_confidence * 100}%` }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      {selectedTx.behavioral_score != null && (
                        <div className="bg-white/60 rounded-lg p-3 border border-blue-100">
                          <div className="text-[10px] text-ink-muted uppercase tracking-wider mb-1">Behavioral Score</div>
                          <div className="text-sm font-semibold text-ink">{selectedTx.behavioral_score.toFixed(3)}</div>
                          <div className="mt-2">
                            <div className="flex items-center justify-between text-[10px] text-ink-muted mb-1">
                              <span>Anomaly Level</span>
                              <span className={`font-semibold ${
                                Math.abs(selectedTx.behavioral_score) > 3 ? 'text-red-600' :
                                Math.abs(selectedTx.behavioral_score) > 2 ? 'text-amber-600' :
                                'text-emerald-600'
                              }`}>
                                {Math.abs(selectedTx.behavioral_score) > 3 ? 'High' :
                                 Math.abs(selectedTx.behavioral_score) > 2 ? 'Medium' : 'Low'}
                              </span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div 
                                className={`h-1.5 rounded-full transition-all ${
                                  Math.abs(selectedTx.behavioral_score) > 3 ? 'bg-red-500' :
                                  Math.abs(selectedTx.behavioral_score) > 2 ? 'bg-amber-500' :
                                  'bg-emerald-500'
                                }`}
                                style={{ width: `${Math.min(Math.abs(selectedTx.behavioral_score) * 20, 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Rule Results — the explainability section */}
                <div>
                  <h4 className="text-sm font-semibold text-ink mb-3">Rule Evaluation Results</h4>
                  {txDetailLoading ? (
                    <div className="text-center py-6">
                      <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-2" />
                      <p className="text-xs text-ink-muted">Loading rule results...</p>
                    </div>
                  ) : selectedTx.rule_results.length === 0 ? (
                    <p className="text-xs text-ink-light py-4 text-center">No rule results recorded for this transaction.</p>
                  ) : (
                    <div className="space-y-2">
                      {selectedTx.rule_results.map((r: RuleResult, i: number) => (
                        <div key={i} className={`rounded-lg border p-3 ${r.triggered ? (RULE_TYPE_STYLES[r.rule_type] || 'bg-gray-50 border-gray-200') : 'bg-bg-alt border-border-light'}`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-ink">{r.rule_id} — {r.rule_name}</span>
                            <div className="flex items-center gap-2">
                              {r.triggered && (
                                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                                  r.rule_type === 'sanctions' ? 'bg-red-100 text-red-700' :
                                  r.rule_type === 'pep' ? 'bg-orange-100 text-orange-700' :
                                  r.rule_type === 'threshold' ? 'bg-amber-100 text-amber-700' :
                                  'bg-blue-100 text-blue-700'
                                }`}>{r.rule_type}</span>
                              )}
                              <span className={`text-[10px] font-medium ${r.triggered ? 'text-red-600' : 'text-emerald-600'}`}>
                                {r.triggered ? 'TRIGGERED' : 'Passed'}
                              </span>
                            </div>
                          </div>
                          {r.triggered && r.detail && (
                            <p className="text-[11px] text-ink-secondary mt-1">{r.detail}</p>
                          )}
                          {r.latency_ms != null && (
                            <p className="text-[10px] text-ink-light mt-1">{r.latency_ms}ms</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Pipeline Stages */}
                {selectedTx.pipeline_stages && selectedTx.pipeline_stages.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Processing Pipeline ({selectedTx.pipeline_stages.length} stages)
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedTx.pipeline_stages.map((stage: string, i: number) => (
                        <div key={i} className="flex items-center gap-1.5">
                          <div className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold">
                            {i + 1}
                          </div>
                          <span className="text-xs text-ink-secondary bg-bg-alt px-2 py-1 rounded-md border border-border-light">
                            {stage.replace(/_/g, ' ')}
                          </span>
                          {i < selectedTx.pipeline_stages.length - 1 && (
                            <svg className="w-3 h-3 text-ink-light" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                            </svg>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* RAG Retrieved Context */}
                {selectedTx.rag_context && (selectedTx.rag_context.policies?.length || selectedTx.rag_context.sanctions_matches?.length || selectedTx.rag_context.similar_precedents?.length) ? (
                  <div className="rounded-xl border border-border-light bg-gradient-to-br from-indigo-50/40 to-white p-4">
                    <h4 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      RAG Retrieved Context
                    </h4>
                    <div className="space-y-3">
                      {selectedTx.rag_context.sanctions_matches?.length > 0 && (
                        <div>
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-red-600 mb-1">⚠ Sanctions Matches</div>
                          <div className="space-y-1">
                            {selectedTx.rag_context.sanctions_matches.map((m, i) => (
                              <div key={i} className="flex items-center justify-between text-xs bg-red-50 border border-red-100 rounded-md px-2.5 py-1.5">
                                <span className="font-medium text-ink">{m.name}</span>
                                <span className="text-red-600 font-semibold">{((m.similarity_score ?? 0) * 100).toFixed(0)}% · {m.program}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedTx.rag_context.policies?.length > 0 && (
                        <div>
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted mb-1">Relevant Policies</div>
                          <div className="space-y-1">
                            {selectedTx.rag_context.policies.map((p, i) => (
                              <div key={i} className="flex items-center justify-between text-xs bg-white border border-border-light rounded-md px-2.5 py-1.5">
                                <span className="text-ink">{p.title}</span>
                                <span className="text-ink-light">{((p.score ?? 0) * 100).toFixed(0)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedTx.rag_context.similar_precedents?.length > 0 && (
                        <div>
                          <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted mb-1">Similar Precedents</div>
                          <div className="space-y-1">
                            {selectedTx.rag_context.similar_precedents.map((pr, i) => (
                              <div key={i} className="flex items-center justify-between text-xs bg-white border border-border-light rounded-md px-2.5 py-1.5">
                                <span className="text-ink truncate max-w-[70%]">{pr.case_summary}</span>
                                <span className={`font-semibold capitalize ${pr.decision === 'blocked' ? 'text-red-600' : pr.decision === 'flagged' ? 'text-amber-600' : 'text-emerald-600'}`}>{pr.decision}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}

                {/* Actions */}
                <div className="flex items-center justify-between pt-3 border-t border-border-light">
                  <button
                    onClick={() => { handleDelete(selectedTx.id); }}
                    className="text-xs text-red-600 hover:text-red-700 px-3 py-2 rounded-lg bg-red-50 hover:bg-red-100 transition-colors"
                  >
                    Delete Transaction
                  </button>
                  <button
                    onClick={() => setSelectedTx(null)}
                    className="text-sm text-ink-muted hover:text-ink px-4 py-2 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Export Report Modal */}
        {showExportModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={() => setShowExportModal(false)}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div className="relative w-full max-w-md bg-white border border-border rounded-2xl shadow-2xl p-6" onClick={e => e.stopPropagation()}>
              <h3 className="text-lg font-bold text-ink mb-1">Export Report</h3>
              <p className="text-sm text-ink-muted mb-4">Download transactions as CSV. Leave dates empty to export all.</p>

              <div className="space-y-4">
                <div>
                  <label htmlFor="export_start_date" className="block text-xs font-medium text-ink-muted mb-1">Start Date</label>
                  <input id="export_start_date" type="date" value={exportStartDate} onChange={e => setExportStartDate(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" />
                </div>
                <div>
                  <label htmlFor="export_end_date" className="block text-xs font-medium text-ink-muted mb-1">End Date</label>
                  <input id="export_end_date" type="date" value={exportEndDate} onChange={e => setExportEndDate(e.target.value)} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" />
                </div>
                {(exportStartDate || exportEndDate) && (
                  <div className="p-3 rounded-lg bg-accent/5 border border-accent/10">
                    <p className="text-xs text-accent-dark">
                      {exportStartDate && exportEndDate
                        ? `Exporting from ${formatDate(exportStartDate)} to ${formatDate(exportEndDate)}`
                        : exportStartDate
                        ? `Exporting from ${formatDate(exportStartDate)} onwards`
                        : `Exporting up to ${formatDate(exportEndDate)}`
                      }
                    </p>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 mt-6">
                <button onClick={() => setShowExportModal(false)} className="px-4 py-2 text-sm text-ink-muted hover:text-ink transition-colors">Cancel</button>
                <button
                  onClick={handleExport}
                  className="bg-accent hover:bg-accent-dark text-white text-sm font-semibold px-6 py-2 rounded-xl transition-all"
                >
                  Download CSV
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PlatformLayout>
  );
}

function InfoRow({ label, value, full }: { label: string; value: string; full?: boolean }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <div className="text-[10px] text-ink-muted uppercase tracking-wider">{label}</div>
      <div className="text-sm text-ink font-medium mt-0.5">{value}</div>
    </div>
  );
}
