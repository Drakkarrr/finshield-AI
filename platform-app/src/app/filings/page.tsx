'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useAuth, useCan } from '@/contexts/AuthContext';
import { api, errorMessage, Filing } from '@/lib/api';
import { FILING_APPROVAL_ROLE, hasRole } from '@/lib/permissions';
import {
  Alert, Badge, Button, Card, EmptyState, InfoRow, Input, LoadingState, Modal, PageHeader, Pagination, Select,
  StatusBadge, Textarea, humanize,
} from '@/components/ui';
import { formatDateTime, timeAgo } from '@/lib/format';

const PAGE_SIZE = 25;
const STATUSES = ['draft', 'under_review', 'submitted', 'confirmed', 'rejected'];

function daysUntil(deadline: string | null): number | null {
  if (!deadline) return null;
  return Math.ceil((new Date(deadline).getTime() - Date.now()) / 86400000);
}

function Filings() {
  const [status, setStatus] = useState('');
  const [type, setType] = useState('');
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Filing | null>(null);
  const [notice, setNotice] = useState('');
  const filings = useSWR(['filings', status, type], () => api.listFilings(status || undefined, type || undefined));
  const all = filings.data ?? [];
  const shown = all.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <PageHeader title="Regulatory filings" description="SAR / STR filings for confirmed suspicious activity. Drafts are created from a case." />
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}

      <div className="flex flex-wrap gap-3">
        <Select
          label="Status"
          className="w-48"
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(0); }}
          options={[{ value: '', label: 'All statuses' }, ...STATUSES.map((s) => ({ value: s, label: humanize(s) }))]}
        />
        <Select
          label="Type"
          className="w-40"
          value={type}
          onChange={(e) => { setType(e.target.value); setPage(0); }}
          options={[{ value: '', label: 'All types' }, { value: 'SAR', label: 'SAR' }, { value: 'STR', label: 'STR' }]}
        />
      </div>

      {filings.isLoading && !filings.data ? (
        <Card><LoadingState label="Loading filings…" /></Card>
      ) : filings.error ? (
        <Alert tone="danger" title="Could not load filings">{errorMessage(filings.error)}</Alert>
      ) : all.length === 0 ? (
        <Card><EmptyState title="No filings found." description="An investigator drafts a filing from a case (Cases → Manage)." /></Card>
      ) : (
        <Card padding="none">
          <ul className="divide-y divide-border-light">
            {shown.map((f) => {
              const days = daysUntil(f.deadline);
              const open = !['submitted', 'confirmed', 'rejected'].includes(f.status);
              return (
                <li key={f.id} className="p-5 flex flex-wrap items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-sm font-semibold text-ink">{f.filing_type}</h2>
                      <StatusBadge status={f.status} />
                      {open && days !== null && days < 0 && <Badge tone="danger">Overdue by {Math.abs(days)} days</Badge>}
                      {open && days !== null && days >= 0 && days <= 7 && <Badge tone="warning">Due in {days} days</Badge>}
                    </div>
                    <p className="mt-2 text-xs text-ink-muted">
                      Case <span className="font-mono">{f.case_id}</span> · Created {timeAgo(f.created_at)}
                      {f.deadline && <> · Deadline {formatDateTime(f.deadline)}</>}
                      {f.reference_number && <> · Reference {f.reference_number}</>}
                    </p>
                    {f.narrative && <p className="mt-2 text-sm text-ink-secondary line-clamp-2">{f.narrative}</p>}
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => setSelected(f)} aria-label={`Open ${f.filing_type} filing ${f.id}`}>Open</Button>
                </li>
              );
            })}
          </ul>
          <Pagination label="Filings pages" page={page} pageSize={PAGE_SIZE} total={all.length} onPageChange={setPage} />
        </Card>
      )}

      {selected && (
        <FilingModal
          filing={selected}
          onClose={() => setSelected(null)}
          onChanged={(msg) => { setSelected(null); setNotice(msg); filings.mutate(); }}
        />
      )}
    </div>
  );
}

function FilingModal({ filing, onClose, onChanged }: { filing: Filing; onClose: () => void; onChanged: (msg: string) => void }) {
  const can = useCan();
  const { user } = useAuth();
  const [narrative, setNarrative] = useState(filing.narrative ?? '');
  const [reference, setReference] = useState(filing.reference_number ?? '');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const canEdit = can(['PATCH', '/api/v1/filings/{filing_id}']);
  const canApprove = canEdit && hasRole(user?.role, FILING_APPROVAL_ROLE);
  const canDelete = can(['DELETE', '/api/v1/filings/{filing_id}']) && filing.status === 'draft';

  const update = async (label: string, changes: { status?: string; narrative?: string; reference_number?: string }) => {
    setBusy(label);
    setError('');
    try {
      await api.updateFiling(filing.id, changes);
      onChanged(`Filing ${filing.id.slice(0, 8)}…: ${label.toLowerCase()}.`);
    } catch (e) {
      setError(errorMessage(e, 'Update failed.'));
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!window.confirm('Delete this draft filing?')) return;
    setBusy('delete');
    try {
      await api.deleteFiling(filing.id);
      onChanged('Draft filing deleted.');
    } catch (e) {
      setError(errorMessage(e, 'Delete failed.'));
      setBusy(null);
    }
  };

  const actions: React.ReactNode[] = [];
  if (canEdit && filing.status === 'draft') {
    actions.push(<Button key="review" onClick={() => update('Sent for review', { status: 'under_review', narrative })} loading={busy === 'Sent for review'}>Send for review</Button>);
  }
  if (canEdit && filing.status === 'under_review') {
    actions.push(<Button key="reject" variant="danger" onClick={() => update('Rejected', { status: 'rejected' })} loading={busy === 'Rejected'}>Reject</Button>);
  }
  if (canApprove && filing.status === 'under_review') {
    actions.push(<Button key="submit" onClick={() => update('Submitted', { status: 'submitted', reference_number: reference || undefined })} loading={busy === 'Submitted'}>Mark as submitted</Button>);
  }
  if (canApprove && filing.status === 'submitted') {
    actions.push(<Button key="confirm" onClick={() => update('Confirmed', { status: 'confirmed', reference_number: reference || undefined })} loading={busy === 'Confirmed'}>Confirm filing</Button>);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`${filing.filing_type} filing`}
      description={filing.id}
      size="3xl"
      footer={
        <>
          {canDelete && <Button variant="danger" onClick={remove} loading={busy === 'delete'}>Delete draft</Button>}
          {actions}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </>
      }
    >
      <div className="space-y-4">
        <StatusBadge status={filing.status} />
        {error && <Alert tone="danger">{error}</Alert>}
        <dl className="grid grid-cols-2 gap-4 rounded-lg border border-border-light bg-surface-hover p-4">
          <InfoRow label="Case" value={<span className="font-mono">{filing.case_id}</span>} />
          <InfoRow label="Created" value={formatDateTime(filing.created_at)} />
          {filing.deadline && <InfoRow label="Deadline" value={formatDateTime(filing.deadline)} />}
          {filing.submitted_at && <InfoRow label="Submitted" value={formatDateTime(filing.submitted_at)} />}
          {filing.confirmed_at && <InfoRow label="Confirmed" value={formatDateTime(filing.confirmed_at)} />}
        </dl>

        {canEdit && filing.status === 'draft' ? (
          <div className="space-y-2">
            <Textarea label="Narrative" rows={6} value={narrative} onChange={(e) => setNarrative(e.target.value)} />
            <Button variant="secondary" size="sm" onClick={() => update('Narrative saved', { narrative })} loading={busy === 'Narrative saved'}>Save narrative</Button>
          </div>
        ) : (
          <section aria-labelledby="narrative-h">
            <h3 id="narrative-h" className="text-sm font-medium text-ink mb-1">Narrative</h3>
            <p className="whitespace-pre-wrap text-sm text-ink-secondary rounded-lg border border-border p-3">{filing.narrative || 'No narrative provided.'}</p>
          </section>
        )}

        {canApprove && ['under_review', 'submitted'].includes(filing.status) && (
          <Input label="Regulator reference number" value={reference} onChange={(e) => setReference(e.target.value)} helpText="Optional; saved with the submit / confirm action." />
        )}
        {canEdit && !canApprove && filing.status === 'under_review' && (
          <p className="text-xs text-ink-muted">Submitting to the regulator needs the {FILING_APPROVAL_ROLE} role.</p>
        )}

        {filing.structured_data && (
          <section aria-labelledby="sd-h">
            <h3 id="sd-h" className="text-sm font-medium text-ink mb-1">Transaction details</h3>
            <pre className="overflow-x-auto text-xs text-ink rounded-lg border border-border p-3">{JSON.stringify(filing.structured_data, null, 2)}</pre>
          </section>
        )}
      </div>
    </Modal>
  );
}

export default function FilingsPage() {
  return (
    <PlatformLayout>
      <Filings />
    </PlatformLayout>
  );
}
