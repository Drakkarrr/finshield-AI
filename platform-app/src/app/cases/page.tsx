'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useCan } from '@/contexts/AuthContext';
import { api, CaseData, errorMessage } from '@/lib/api';
import {
  Alert, Badge, Button, Card, EmptyState, FilterChips, Input, LoadingState, Modal, PageHeader, Pagination, Select,
  StatusBadge, Tabs, TabPanel, Textarea, Tone, humanize,
} from '@/components/ui';
import { formatCurrency, formatDateTime, timeAgo } from '@/lib/format';

const PAGE_SIZE = 25;

const PRIORITY_TONES: Record<string, Tone> = { critical: 'danger', high: 'danger', medium: 'warning', low: 'neutral' };
const PRIORITIES = ['low', 'medium', 'high', 'critical'].map((p) => ({ value: p, label: humanize(p) }));

// Statuses the API's CaseResponse model accepts (backend/app/models.py CaseStatus).
const NEXT_STATUS: Record<string, string[]> = {
  created: ['open', 'under_review'],
  open: ['under_review', 'escalated', 'resolved'],
  under_review: ['escalated', 'resolved'],
  escalated: ['resolved'],
  resolved: ['closed'],
  closed: [],
};

const GROUPS: Record<string, string[]> = {
  open: ['created', 'open', 'under_review'],
  escalated: ['escalated'],
  resolved: ['resolved', 'closed'],
};

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'resolved', label: 'Resolved' },
] as const;
type Filter = (typeof FILTERS)[number]['value'];

function Cases() {
  const can = useCan();
  const cases = useSWR('cases', api.listCases);
  const [filter, setFilter] = useState<Filter>('all');
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState<CaseData | null>(null);
  const [notice, setNotice] = useState<{ tone: Tone; text: string } | null>(null);
  const [sweeping, setSweeping] = useState(false);

  const all = cases.data ?? [];
  const filtered = filter === 'all' ? all : all.filter((c) => GROUPS[filter].includes(c.status));
  const shown = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const count = (g: string) => all.filter((c) => GROUPS[g].includes(c.status)).length;

  const runSla = async () => {
    setSweeping(true);
    try {
      const r = await api.checkSla();
      setNotice({ tone: 'success', text: `SLA sweep finished: ${r.escalated} case(s) escalated, ${r.approaching_notified} approaching-deadline notification(s) sent.` });
      cases.mutate();
    } catch (e) {
      setNotice({ tone: 'danger', text: errorMessage(e, 'SLA sweep failed.') });
    } finally {
      setSweeping(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cases"
        description="Compliance cases and investigations"
        actions={
          <>
            {can(['POST', '/api/v1/cases/check-sla']) && (
              <Button variant="secondary" onClick={runSla} loading={sweeping}>Run SLA check now</Button>
            )}
            <Button onClick={() => setShowCreate(!showCreate)} aria-expanded={showCreate} aria-controls="create-case">
              {showCreate ? 'Close form' : 'Create case'}
            </Button>
          </>
        }
      />

      {notice && <Alert tone={notice.tone} onDismiss={() => setNotice(null)}>{notice.text}</Alert>}

      {showCreate && (
        <CreateCase
          canAggregate={can(['POST', '/api/v1/cases/aggregate'])}
          onDone={(text) => { setShowCreate(false); setNotice({ tone: 'success', text }); cases.mutate(); }}
        />
      )}

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total', value: all.length, cls: 'text-ink' },
          { label: 'Open', value: count('open'), cls: 'text-info-fg' },
          { label: 'Escalated', value: count('escalated'), cls: 'text-danger-fg' },
          { label: 'Resolved', value: count('resolved'), cls: 'text-success-fg' },
        ].map((s) => (
          <Card key={s.label} padding="sm" className="text-center flex flex-col-reverse">
            <dt className="text-xs text-ink-muted mt-1">{s.label}</dt>
            <dd className={`text-2xl font-bold ${s.cls}`}>{s.value}</dd>
          </Card>
        ))}
      </dl>

      <FilterChips label="Filter cases by status" options={FILTERS} value={filter} onChange={(f) => { setFilter(f); setPage(0); }} />

      {cases.isLoading && !cases.data ? (
        <Card><LoadingState label="Loading cases…" /></Card>
      ) : cases.error ? (
        <Alert tone="danger" title="Could not load cases">{errorMessage(cases.error)}</Alert>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState title={all.length === 0 ? 'No cases yet.' : 'No cases match this filter.'} description={all.length === 0 ? 'Create one from a flagged or blocked transaction.' : undefined} />
        </Card>
      ) : (
        <Card padding="none">
          <ul className="divide-y divide-border-light">
            {shown.map((c) => (
              <li key={c.case_id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-mono text-sm font-semibold text-ink">{c.case_id}</h2>
                    <Badge tone={PRIORITY_TONES[c.priority] ?? 'neutral'}>{humanize(c.priority)} priority</Badge>
                    <StatusBadge status={c.status} />
                  </div>
                  <div className="flex items-center gap-2">
                    <time className="text-xs text-ink-muted" dateTime={c.created_at} title={formatDateTime(c.created_at)}>{timeAgo(c.created_at)}</time>
                    <Button variant="secondary" size="sm" onClick={() => setSelected(c)} aria-label={`Manage case ${c.case_id}`}>Manage</Button>
                  </div>
                </div>
                <p className="text-sm text-ink-secondary mb-2">{c.reason}</p>
                <p className="text-xs text-ink-muted">
                  Transaction <span className="font-mono">{c.transaction_id}</span> · Assigned to {c.assigned_to || 'nobody'}
                </p>
              </li>
            ))}
          </ul>
          <Pagination label="Cases pages" page={page} pageSize={PAGE_SIZE} total={filtered.length} onPageChange={setPage} />
        </Card>
      )}

      {selected && (
        <CaseModal
          caseData={selected}
          onClose={() => setSelected(null)}
          onChanged={(text) => { cases.mutate(); setSelected(null); if (text) setNotice({ tone: 'success', text }); }}
        />
      )}
    </div>
  );
}

function CreateCase({ canAggregate, onDone }: { canAggregate: boolean; onDone: (message: string) => void }) {
  const txs = useSWR('transactions:for-cases', () => api.listTransactions(100, 0));
  const [form, setForm] = useState({ transaction_id: '', reason: '', priority: 'medium' });
  const [aggregate, setAggregate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (aggregate) {
        const r = await api.aggregateCase(form);
        onDone(r.aggregated ? `Attached to existing case ${r.case_id}.` : `Case ${r.case_id} created.`);
      } else {
        const c = await api.createCase(form);
        onDone(`Case ${c.case_id} created.`);
      }
    } catch (err) {
      setError(errorMessage(err, 'Failed to create case.'));
    } finally {
      setSaving(false);
    }
  };

  const items = txs.data?.items ?? [];
  return (
    <Card as="section" padding="lg" id="create-case" aria-labelledby="create-case-h">
      <h2 id="create-case-h" className="text-sm font-semibold text-ink mb-4">Create a case</h2>
      {txs.isLoading ? <LoadingState label="Loading transactions…" /> : items.length === 0 ? (
        <p className="text-sm text-ink-muted">No transactions yet. Screen a transaction first.</p>
      ) : (
        <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Select
            label="Transaction (100 most recent)"
            value={form.transaction_id}
            onChange={(e) => setForm({ ...form, transaction_id: e.target.value })}
            required
            options={[
              { value: '', label: 'Select a transaction…' },
              ...items.map((t) => ({ value: t.id, label: `${t.sender} → ${t.receiver} · ${formatCurrency(t.amount, t.currency)} · ${humanize(t.status)}` })),
            ]}
          />
          <Input label="Reason" placeholder="e.g. Suspicious wire pattern" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} required />
          <Select label="Priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} options={PRIORITIES} />
          {canAggregate && (
            <label className="md:col-span-3 flex items-center gap-2 text-sm text-ink-secondary">
              <input type="checkbox" checked={aggregate} onChange={(e) => setAggregate(e.target.checked)} className="w-4 h-4 accent-accent" />
              Attach to an existing open case for the same sender if there is one
            </label>
          )}
          <div className="md:col-span-3 flex justify-end">
            <Button type="submit" loading={saving}>Create case</Button>
          </div>
        </form>
      )}
      {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
    </Card>
  );
}

const MODAL_TABS = [
  { id: 'manage', label: 'Manage' },
  { id: 'comments', label: 'Comments' },
  { id: 'notes', label: 'Investigator notes' },
];

function CaseModal({ caseData, onClose, onChanged }: { caseData: CaseData; onClose: () => void; onChanged: (message?: string) => void }) {
  const can = useCan();
  const [tab, setTab] = useState('manage');
  const [error, setError] = useState('');
  const canDelete = can(['DELETE', '/api/v1/cases/{case_id}']);

  const remove = async () => {
    if (!window.confirm(`Delete case ${caseData.case_id}? Only cases outside the retention window and without linked filings can be deleted.`)) return;
    try {
      await api.deleteCase(caseData.case_id);
      onChanged(`Case ${caseData.case_id} deleted.`);
    } catch (e) {
      setError(errorMessage(e, 'Failed to delete case.'));
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={caseData.case_id}
      description={caseData.reason}
      size="xl"
      footer={
        <>
          {canDelete && <Button variant="danger" onClick={remove}>Delete case</Button>}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          <StatusBadge status={caseData.status} />
          <Badge tone={PRIORITY_TONES[caseData.priority] ?? 'neutral'}>{humanize(caseData.priority)} priority</Badge>
          <span>Transaction <span className="font-mono">{caseData.transaction_id}</span></span>
          <span>· Created {formatDateTime(caseData.created_at)}</span>
        </div>
        {error && <Alert tone="danger">{error}</Alert>}
        <Tabs idPrefix="case" label="Case sections" tabs={MODAL_TABS} value={tab} onChange={setTab} />
        <TabPanel idPrefix="case" id={tab}>
          {tab === 'manage' && <ManageTab caseData={caseData} onChanged={onChanged} />}
          {tab === 'comments' && <CommentsTab caseId={caseData.case_id} />}
          {tab === 'notes' && <NotesTab caseId={caseData.case_id} />}
        </TabPanel>
      </div>
    </Modal>
  );
}

function ManageTab({ caseData, onChanged }: { caseData: CaseData; onChanged: (message?: string) => void }) {
  const can = useCan();
  const [status, setStatus] = useState(caseData.status);
  const [assignedTo, setAssignedTo] = useState(caseData.assigned_to || '');
  const [filingType, setFilingType] = useState('SAR');
  const [narrative, setNarrative] = useState('');
  const [busy, setBusy] = useState<'save' | 'filing' | null>(null);
  const [error, setError] = useState('');
  const canUpdate = can(['PATCH', '/api/v1/cases/{case_id}']);
  const canFile = can(['POST', '/api/v1/filings']);
  const next = NEXT_STATUS[caseData.status] ?? [];

  const save = async () => {
    setBusy('save');
    setError('');
    try {
      await api.updateCase(caseData.case_id, {
        status: status !== caseData.status ? status : undefined,
        assigned_to: assignedTo !== (caseData.assigned_to || '') ? assignedTo : undefined,
      });
      onChanged(`Case ${caseData.case_id} updated.`);
    } catch (e) {
      setError(errorMessage(e, 'Failed to update case.'));
    } finally {
      setBusy(null);
    }
  };

  const draftFiling = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy('filing');
    setError('');
    try {
      const f = await api.createFiling(caseData.case_id, filingType, narrative || undefined);
      onChanged(`${f.filing_type} draft ${f.id.slice(0, 8)}… created — continue on the Filings page.`);
    } catch (err) {
      setError(errorMessage(err, 'Failed to create the filing.'));
    } finally {
      setBusy(null);
    }
  };

  if (!canUpdate && !canFile) {
    return <p className="text-sm text-ink-muted">Changing status or assignment needs the investigator role. You can comment and add notes.</p>;
  }

  return (
    <div className="space-y-6">
      {error && <Alert tone="danger">{error}</Alert>}
      {canUpdate && (
        <section aria-labelledby="case-update-h" className="space-y-4">
          <h3 id="case-update-h" className="text-sm font-semibold text-ink">Status and assignment</h3>
          <Select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            disabled={next.length === 0}
            helpText={next.length === 0 ? 'This case is closed.' : undefined}
            options={[caseData.status, ...next].map((s) => ({ value: s, label: s === caseData.status ? `${humanize(s)} (current)` : humanize(s) }))}
          />
          <Input label="Assigned to" placeholder="Analyst name or team" value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)} />
          <Button onClick={save} loading={busy === 'save'}>Save changes</Button>
        </section>
      )}
      {canFile && (
        <section aria-labelledby="case-filing-h">
          <h3 id="case-filing-h" className="text-sm font-semibold text-ink mb-3">Draft a regulatory filing</h3>
          <form onSubmit={draftFiling} className="space-y-3">
            <Select label="Filing type" value={filingType} onChange={(e) => setFilingType(e.target.value)} options={[
              { value: 'SAR', label: 'SAR — Suspicious Activity Report' },
              { value: 'STR', label: 'STR — Suspicious Transaction Report' },
            ]} />
            <Textarea label="Narrative (optional)" rows={3} value={narrative} onChange={(e) => setNarrative(e.target.value)} />
            <Button type="submit" variant="secondary" loading={busy === 'filing'}>Create draft filing</Button>
          </form>
          <p className="text-xs text-ink-muted mt-2">
            Drafts are reviewed and submitted on the <Link href="/filings">Filings</Link> page.
          </p>
        </section>
      )}
    </div>
  );
}

function CommentsTab({ caseId }: { caseId: string }) {
  const comments = useSWR(['case-comments', caseId], () => api.listCaseComments(caseId));
  const [body, setBody] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.addCaseComment(caseId, body.trim());
      setBody('');
      comments.mutate();
    } catch (err) {
      setError(errorMessage(err, 'Failed to post comment.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted">Comments are part of the case record and visible to everyone in your organisation.</p>
      {comments.isLoading ? <LoadingState label="Loading comments…" /> : (comments.data ?? []).length === 0 ? (
        <p className="text-sm text-ink-muted">No comments yet.</p>
      ) : (
        <ul className="space-y-2 max-h-60 overflow-y-auto">
          {comments.data!.map((c) => (
            <li key={c.id} className="bg-bg-alt rounded-lg px-3 py-2">
              <p className="text-sm text-ink-secondary whitespace-pre-wrap">{c.body}</p>
              <p className="text-2xs text-ink-muted mt-1">{formatDateTime(c.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      {error && <Alert tone="danger">{error}</Alert>}
      <form onSubmit={submit} className="space-y-2">
        <Textarea label="New comment" rows={2} value={body} onChange={(e) => setBody(e.target.value)} required />
        <Button type="submit" size="sm" loading={saving} disabled={!body.trim()}>Post comment</Button>
      </form>
    </div>
  );
}

function NotesTab({ caseId }: { caseId: string }) {
  const notes = useSWR(['case-notes', caseId], () => api.listCaseNotes(caseId));
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.addCaseNote(caseId, note.trim());
      setNote('');
      notes.mutate();
    } catch (err) {
      setError(errorMessage(err, 'Failed to save note.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted">Working notes for investigators. Unlike comments they are not written to the audit trail.</p>
      {notes.isLoading ? <LoadingState label="Loading notes…" /> : (notes.data ?? []).length === 0 ? (
        <p className="text-sm text-ink-muted">No notes yet.</p>
      ) : (
        <ul className="space-y-2 max-h-60 overflow-y-auto">
          {notes.data!.map((n) => (
            <li key={n.id} className="bg-bg-alt rounded-lg px-3 py-2">
              <p className="text-sm text-ink-secondary whitespace-pre-wrap">{n.note}</p>
              <p className="text-2xs text-ink-muted mt-1">{formatDateTime(n.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      {error && <Alert tone="danger">{error}</Alert>}
      <form onSubmit={submit} className="space-y-2">
        <Textarea label="New note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} required />
        <Button type="submit" size="sm" loading={saving} disabled={!note.trim()}>Add note</Button>
      </form>
    </div>
  );
}

export default function CasesPage() {
  return (
    <PlatformLayout>
      <Cases />
    </PlatformLayout>
  );
}
