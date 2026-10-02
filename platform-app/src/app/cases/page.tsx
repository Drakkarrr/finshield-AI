'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { api, CaseData, CaseComment, TransactionListItem } from '@/lib/api';
import { formatCurrency, formatNumber, formatDateTime, timeAgo } from '@/lib/format';

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'text-red-600 bg-red-50',
  high: 'text-orange-600 bg-orange-50',
  medium: 'text-amber-600 bg-amber-50',
  low: 'text-ink-muted bg-gray-100',
};

const STATUS_COLORS: Record<string, string> = {
  created: 'text-blue-600 bg-blue-50',
  open: 'text-blue-600 bg-blue-50',
  under_review: 'text-amber-600 bg-amber-50',
  in_progress: 'text-amber-600 bg-amber-50',
  escalated: 'text-red-600 bg-red-50',
  resolved: 'text-emerald-600 bg-emerald-50',
  closed: 'text-emerald-600 bg-emerald-50',
};

const VALID_TRANSITIONS: Record<string, string[]> = {
  created: ['open', 'under_review'],
  open: ['under_review', 'escalated', 'resolved'],
  under_review: ['in_progress', 'escalated', 'resolved'],
  in_progress: ['escalated', 'resolved'],
  escalated: ['resolved'],
  resolved: ['closed'],
  closed: [],
};

function statusLabel(s: string): string {
  return s.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// Group the 6 raw statuses into 4 buckets shared by stats + filters
const STATUS_GROUPS: Record<string, string[]> = {
  open: ['created', 'open', 'under_review', 'in_progress'],
  escalated: ['escalated'],
  resolved: ['resolved', 'closed'],
};

function inGroup(status: string, group: string): boolean {
  return (STATUS_GROUPS[group] || []).includes(status);
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [newCase, setNewCase] = useState({ transaction_id: '', reason: '', priority: 'medium' });
  const [selectedCase, setSelectedCase] = useState<CaseData | null>(null);
  const [availableTxs, setAvailableTxs] = useState<TransactionListItem[]>([]);

  const loadCases = useCallback(async () => {
    try {
      const data = await api.listCases();
      setCases(data);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Unable to load cases.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCases();
    api.listTransactions(50, 0).then(setAvailableTxs).catch(() => {});
  }, [loadCases]);

  const filtered = filter === 'all' ? cases : cases.filter(c => inGroup(c.status, filter));

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      const created = await api.createCase({
        transaction_id: newCase.transaction_id,
        reason: newCase.reason,
        priority: newCase.priority,
      });
      setCases([created, ...cases]);
      setShowCreate(false);
      setNewCase({ transaction_id: '', reason: '', priority: 'medium' });
    } catch (e: any) {
      setError(e.message || 'Failed to create case.');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCase = async (caseId: string) => {
    if (!confirm('Delete this case and its comments? This cannot be undone.')) return;
    try {
      await api.deleteCase(caseId);
      setCases(cases.filter(c => c.case_id !== caseId));
      if (selectedCase?.case_id === caseId) setSelectedCase(null);
    } catch (e: any) {
      setError(e.message || 'Failed to delete case.');
    }
  };

  return (
    <PlatformLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">Cases</h1>
            <p className="text-sm text-ink-muted mt-0.5">Manage compliance cases and investigations</p>
          </div>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-4 py-2.5 rounded-xl transition-all"
          >
            {showCreate ? 'Close' : '+ Create Case'}
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>
        )}

        {/* Create Case Form */}
        {showCreate && (
          <div className="glass p-6 animate-fade-in-up">
            <h3 className="text-sm font-semibold text-ink mb-4">Create New Case</h3>
            {availableTxs.length === 0 ? (
              <p className="text-sm text-ink-light">No transactions available. Screen a transaction first before creating a case.</p>
            ) : (
            <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="case_tx" className="block text-xs font-medium text-ink-muted mb-1">Transaction</label>
                <select id="case_tx" value={newCase.transaction_id} onChange={(e) => setNewCase({ ...newCase, transaction_id: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink" required aria-required="true">
                  <option value="">Select transaction...</option>
                  {availableTxs.map((t) => (
                    <option key={t.id} value={t.id}>{t.sender} → {t.receiver} · {formatCurrency(t.amount, t.currency)} · {t.status}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="case_reason" className="block text-xs font-medium text-ink-muted mb-1">Reason</label>
                <input id="case_reason" placeholder="e.g. Suspicious wire pattern" value={newCase.reason} onChange={(e) => setNewCase({ ...newCase, reason: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light" required aria-required="true" />
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label htmlFor="case_priority" className="block text-xs font-medium text-ink-muted mb-1">Priority</label>
                  <select id="case_priority" value={newCase.priority} onChange={(e) => setNewCase({ ...newCase, priority: e.target.value })} className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button type="submit" disabled={creating} className="bg-accent hover:bg-accent-light text-white font-semibold px-4 py-2.5 rounded-xl transition-all disabled:opacity-50">
                    {creating ? 'Creating...' : 'Create'}
                  </button>
                </div>
              </div>
            </form>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Total', value: cases.length, color: 'text-ink' },
            { label: 'Open', value: cases.filter(c => inGroup(c.status, 'open')).length, color: 'text-blue-600' },
            { label: 'Escalated', value: cases.filter(c => inGroup(c.status, 'escalated')).length, color: 'text-red-600' },
            { label: 'Resolved', value: cases.filter(c => inGroup(c.status, 'resolved')).length, color: 'text-emerald-600' },
          ].map((s) => (
            <div key={s.label} className="glass p-4 text-center">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-ink-muted mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          {['all', 'open', 'escalated', 'resolved'].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === s ? 'bg-accent/10 text-accent-dark' : 'text-ink-muted hover:bg-bg'
              }`}
            >
              {s === 'all' ? 'All' : statusLabel(s)}
            </button>
          ))}
        </div>

        {/* Cases List */}
        {loading ? (
          <div className="glass p-12 text-center">
            <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-ink-muted">Loading cases...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass p-12 text-center">
            <p className="text-sm text-ink-light">
              {cases.length === 0 ? 'No cases yet. Create one from a flagged or blocked transaction.' : 'No cases match this filter.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((c) => (
              <div key={c.case_id} className="glass glass-hover p-5 transition-all duration-300 hover:-translate-y-0.5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-semibold text-ink">{c.case_id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${PRIORITY_COLORS[c.priority] || PRIORITY_COLORS.medium}`}>
                      {c.priority.toUpperCase()}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATUS_COLORS[c.status] || STATUS_COLORS.open}`}>
                      {statusLabel(c.status).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedCase(c)}
                      className="text-xs text-accent-dark hover:text-accent transition-colors px-2 py-1 rounded bg-accent/5 hover:bg-accent/10"
                    >
                      Manage →
                    </button>
                    <button
                      onClick={() => handleDeleteCase(c.case_id)}
                      className="text-xs text-red-600 hover:text-red-700 px-2 py-1 rounded bg-red-50 hover:bg-red-100 transition-colors"
                      title="Delete case"
                    >
                      Delete
                    </button>
                    <span className="text-xs text-ink-light" title={formatDateTime(c.created_at)}>{timeAgo(c.created_at)}</span>
                  </div>
                </div>
                <p className="text-sm text-ink-secondary mb-2">{c.reason}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-ink-light">TX: <span className="font-mono text-ink-muted">{c.transaction_id}</span></span>
                    <span className="text-xs text-ink-light">Assigned: <span className="text-ink-secondary">{c.assigned_to || 'Unassigned'}</span></span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Case Management Modal */}
        {selectedCase && (
          <CaseManagementModal
            caseData={selectedCase}
            onClose={() => setSelectedCase(null)}
            onUpdate={() => { loadCases(); setSelectedCase(null); }}
          />
        )}
      </div>
    </PlatformLayout>
  );
}

// ── Case Management Modal ──
function CaseManagementModal({ caseData, onClose, onUpdate }: { caseData: CaseData; onClose: () => void; onUpdate: () => void }) {
  const [status, setStatus] = useState(caseData.status);
  const [assignedTo, setAssignedTo] = useState(caseData.assigned_to || '');
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [loadingComments, setLoadingComments] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [addingComment, setAddingComment] = useState(false);

  const validNext = VALID_TRANSITIONS[caseData.status] || [];

  useEffect(() => {
    api.listCaseComments(caseData.case_id)
      .then(setComments)
      .catch(() => {})
      .finally(() => setLoadingComments(false));
  }, [caseData.case_id]);

  const handleUpdate = async () => {
    setUpdating(true);
    try {
      await api.updateCase(caseData.case_id, {
        status: status !== caseData.status ? status : undefined,
        assigned_to: assignedTo || undefined,
      });
      onUpdate();
    } catch { /* ignore */ }
    setUpdating(false);
  };

  const handleAddComment = async () => {
    if (!newComment.trim()) return;
    setAddingComment(true);
    try {
      const comment = await api.addCaseComment(caseData.case_id, newComment.trim());
      setComments([...comments, comment]);
      setNewComment('');
    } catch { /* ignore */ }
    setAddingComment(false);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg glass border border-border rounded-2xl shadow-2xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 space-y-5">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">{caseData.case_id}</h3>
              <p className="text-xs text-ink-muted mt-0.5">{caseData.reason}</p>
            </div>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATUS_COLORS[caseData.status]}`}>
              {statusLabel(caseData.status).toUpperCase()}
            </span>
          </div>

          {/* Status Update */}
          {validNext.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Update Status</label>
              <div className="flex flex-wrap gap-2">
                {validNext.map(s => (
                  <button
                    key={s}
                    onClick={() => setStatus(s)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      status === s ? 'bg-accent/10 text-accent-dark ring-1 ring-accent/30' : 'bg-bg text-ink-muted hover:bg-white/10'
                    }`}
                  >
                    {statusLabel(s)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Assignment */}
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">Assigned To</label>
            <input
              value={assignedTo}
              onChange={e => setAssignedTo(e.target.value)}
              placeholder="Analyst name or team"
              className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light"
            />
          </div>

          <button
            onClick={handleUpdate}
            disabled={updating}
            className="w-full bg-accent hover:bg-accent-light text-ink text-sm font-semibold py-2.5 rounded-xl transition-all disabled:opacity-50"
          >
            {updating ? 'Updating...' : 'Save Changes'}
          </button>

          {/* Comments */}
          <div>
            <h4 className="text-sm font-semibold text-ink mb-3">Comments</h4>
            {loadingComments ? (
              <p className="text-xs text-ink-light">Loading comments...</p>
            ) : comments.length === 0 ? (
              <p className="text-xs text-ink-light mb-3">No comments yet.</p>
            ) : (
              <div className="space-y-2 mb-3 max-h-40 overflow-y-auto">
                {comments.map(c => (
                  <div key={c.id} className="bg-bg-alt rounded-lg px-3 py-2">
                    <p className="text-sm text-ink-secondary">{c.body}</p>
                    <span className="text-[10px] text-ink-light">{formatDateTime(c.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <input
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="flex-1 bg-bg border border-border rounded-xl px-4 py-2 text-sm text-ink placeholder-ink-light"
                onKeyDown={e => e.key === 'Enter' && handleAddComment()}
              />
              <button
                onClick={handleAddComment}
                disabled={addingComment || !newComment.trim()}
                className="bg-accent/10 hover:bg-accent/20 text-accent-dark text-sm font-semibold px-4 rounded-xl transition-all disabled:opacity-50"
              >
                {addingComment ? '...' : 'Post'}
              </button>
            </div>
          </div>

          {/* Case Info */}
          <div className="border-t border-border-light pt-3 space-y-1">
            <div className="text-[11px] text-ink-light">Transaction: <span className="font-mono text-ink-muted">{caseData.transaction_id}</span></div>
            <div className="text-[11px] text-ink-light">Priority: <span className={`font-semibold ${PRIORITY_COLORS[caseData.priority]}`}>{caseData.priority.toUpperCase()}</span></div>
            <div className="text-[11px] text-ink-light">Created: {formatDateTime(caseData.created_at)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
