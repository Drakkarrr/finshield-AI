'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { api, errorMessage, PrivacyRequest } from '@/lib/api';
import {
  Alert, Badge, Button, Card, EmptyState, Input, LoadingState, Modal, PageHeader, Select, StatusBadge, Table, TBody,
  Textarea, THead, Td, Th, Tr, humanize,
} from '@/components/ui';
import { formatDate, formatDateTime } from '@/lib/format';

function Privacy() {
  const requests = useSWR('privacy-requests', api.listPrivacyRequests);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const list = requests.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Privacy requests"
        description="Data-subject access and erasure requests. Erasure keeps what AML regulation requires and reports what it retained."
        actions={<Button onClick={() => setCreating(true)}>Log request</Button>}
      />
      {notice && <Alert tone="success" onDismiss={() => setNotice('')}>{notice}</Alert>}

      <Card padding="none">
        {requests.isLoading && !requests.data ? <LoadingState label="Loading requests…" /> : requests.error ? (
          <div className="p-5"><Alert tone="danger">{errorMessage(requests.error)}</Alert></div>
        ) : list.length === 0 ? <EmptyState title="No data-subject requests logged." /> : (
          <Table caption="Data-subject requests, oldest due first">
            <THead><Th>Subject</Th><Th>Type</Th><Th>Status</Th><Th>Received</Th><Th>Due</Th><Th align="right">Actions</Th></THead>
            <TBody>
              {list.map((r) => (
                <Tr key={r.id}>
                  <Th scope="row">
                    <span className="font-mono text-xs">{r.subject_ref_masked}</span>
                    <span className="block text-2xs text-ink-muted font-normal">{humanize(r.subject_type)}</span>
                  </Th>
                  <Td className="text-xs">{humanize(r.request_type)}</Td>
                  <Td>
                    <span className="flex flex-wrap gap-1">
                      <StatusBadge status={r.status} />
                      {r.overdue && <Badge tone="danger">Overdue</Badge>}
                    </span>
                  </Td>
                  <Td className="text-xs text-ink-muted">{formatDate(r.received_at)}</Td>
                  <Td className="text-xs text-ink-muted">{formatDate(r.due_at)}</Td>
                  <Td align="right"><Button variant="secondary" size="sm" onClick={() => setOpenId(r.id)} aria-label={`Open request ${r.id}`}>Open</Button></Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      {creating && (
        <CreateRequestModal
          onClose={() => setCreating(false)}
          onCreated={(r) => { setCreating(false); requests.mutate(); setNotice(`Request logged; due ${formatDate(r.due_at)}.`); }}
        />
      )}
      {openId && (
        <RequestModal
          id={openId}
          onClose={() => setOpenId(null)}
          onExecuted={() => { requests.mutate(); setNotice('Request executed. The outcome is stored with the request.'); }}
        />
      )}
    </div>
  );
}

function CreateRequestModal({ onClose, onCreated }: { onClose: () => void; onCreated: (r: PrivacyRequest) => void }) {
  const [form, setForm] = useState({ subject_type: 'customer' as 'customer' | 'user', subject_ref: '', request_type: 'access' as 'access' | 'erasure', legal_basis_notes: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      onCreated(await api.createPrivacyRequest({ ...form, legal_basis_notes: form.legal_basis_notes || undefined }));
    } catch (err) {
      setError(errorMessage(err, 'Could not log the request.'));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Log a data-subject request" description="The due date follows the privacy.dsar_due_days setting.">
      <form onSubmit={submit} className="space-y-3">
        <Select label="Subject type" value={form.subject_type} onChange={(e) => setForm({ ...form, subject_type: e.target.value as 'customer' | 'user' })}
          options={[{ value: 'customer', label: 'Customer (screened party)' }, { value: 'user', label: 'Platform user' }]} />
        <Input
          label={form.subject_type === 'customer' ? 'Customer name or account id' : 'User email'}
          value={form.subject_ref}
          onChange={(e) => setForm({ ...form, subject_ref: e.target.value })}
          required
          helpText="Stored encrypted; lists show it masked."
        />
        <Select label="Request type" value={form.request_type} onChange={(e) => setForm({ ...form, request_type: e.target.value as 'access' | 'erasure' })}
          options={[{ value: 'access', label: 'Access — export the personal data held' }, { value: 'erasure', label: 'Erasure — delete what may be deleted' }]} />
        <Textarea label="Legal basis / notes (optional)" rows={3} value={form.legal_basis_notes} onChange={(e) => setForm({ ...form, legal_basis_notes: e.target.value })} />
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Log request</Button>
        </div>
      </form>
    </Modal>
  );
}

function RequestModal({ id, onClose, onExecuted }: { id: string; onClose: () => void; onExecuted: () => void }) {
  const req = useSWR(['privacy-request', id], () => api.getPrivacyRequest(id));
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const r = req.data;

  const execute = async () => {
    if (!r) return;
    const warning = r.request_type === 'erasure'
      ? 'Run this erasure now? Deleted personal data cannot be restored; records regulation requires are retained.'
      : 'Run this access export now?';
    if (!window.confirm(warning)) return;
    setRunning(true);
    setError('');
    try {
      await req.mutate(await api.executePrivacyRequest(id), { revalidate: false });
      onExecuted();
    } catch (e) {
      setError(errorMessage(e, 'Execution failed.'));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={r ? `${humanize(r.request_type)} request` : 'Privacy request'}
      description={id}
      size="2xl"
      footer={
        <>
          {r?.status === 'received' && (
            <Button variant={r.request_type === 'erasure' ? 'danger' : 'primary'} onClick={execute} loading={running}>
              {r.request_type === 'erasure' ? 'Run erasure' : 'Run access export'}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </>
      }
    >
      {req.isLoading ? <LoadingState /> : req.error ? <Alert tone="danger">{errorMessage(req.error)}</Alert> : r && (
        <div className="space-y-3 text-sm">
          <p className="flex flex-wrap items-center gap-2">
            <StatusBadge status={r.status} />
            {r.overdue && <Badge tone="danger">Overdue</Badge>}
            <span className="text-ink-secondary">Subject <span className="font-mono">{r.subject_ref_masked}</span> ({r.subject_type})</span>
          </p>
          <p className="text-xs text-ink-muted">
            Received {formatDateTime(r.received_at)} · due {formatDateTime(r.due_at)}
            {r.completed_at && <> · completed {formatDateTime(r.completed_at)}</>}
          </p>
          {r.legal_basis_notes && <p className="text-ink-secondary whitespace-pre-wrap">{r.legal_basis_notes}</p>}
          {error && <Alert tone="danger">{error}</Alert>}
          {r.outcome != null && (
            <>
              <h3 className="text-sm font-semibold text-ink">Outcome</h3>
              <pre className="overflow-x-auto text-xs bg-bg-alt rounded-lg p-3 max-h-80">{JSON.stringify(r.outcome, null, 2)}</pre>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function PrivacyPage() {
  return (
    <PlatformLayout>
      <Privacy />
    </PlatformLayout>
  );
}
