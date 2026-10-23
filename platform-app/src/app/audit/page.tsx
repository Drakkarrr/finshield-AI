'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { api, AuditEntry, AuditFilters, AuditVerification, errorMessage } from '@/lib/api';
import {
  Alert, Badge, Button, Card, CopyButton, EmptyState, Input, LoadingState, Modal, PageHeader, Pagination, Table, TBody,
  THead, Td, Th, Tr, humanize,
} from '@/components/ui';
import { formatDateTime, formatNumber } from '@/lib/format';

const PAGE_SIZE = 50;
const EMPTY: AuditFilters = { actor: '', action: '', resource_type: '', resource_id: '', date_from: '', date_to: '' };

function Audit() {
  const [draft, setDraft] = useState<AuditFilters>(EMPTY);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  const [verification, setVerification] = useState<AuditVerification | null>(null);
  const [busy, setBusy] = useState<'verify' | 'export' | null>(null);
  const [error, setError] = useState('');
  const [showKey, setShowKey] = useState(false);

  const log = useSWR(['audit', filters, page], () => api.listAudit({
    ...filters,
    // <input type="datetime-local"> has no zone; send the user's local time as an absolute instant
    date_from: filters.date_from ? new Date(filters.date_from).toISOString() : undefined,
    date_to: filters.date_to ? new Date(filters.date_to).toISOString() : undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }));

  const verify = async () => {
    setBusy('verify');
    setError('');
    try {
      setVerification(await api.verifyAudit());
      log.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Verification failed.'));
    } finally {
      setBusy(null);
    }
  };

  const exportBundle = async () => {
    setBusy('export');
    setError('');
    try {
      const bundle = await api.exportAudit();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `finshield-audit-${new Date().toISOString().slice(0, 19).replace(/:/g, '')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorMessage(e, 'Export failed.'));
    } finally {
      setBusy(null);
    }
  };

  const apply = (e: React.FormEvent) => { e.preventDefault(); setFilters(draft); setPage(0); };
  const set = (k: keyof AuditFilters) => (e: React.ChangeEvent<HTMLInputElement>) => setDraft({ ...draft, [k]: e.target.value });
  const items = log.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit trail"
        description="Hash-chained, append-only record of every consequential action in your organisation"
        actions={
          <>
            <Button variant="secondary" onClick={() => setShowKey(true)}>Public key</Button>
            <Button variant="secondary" onClick={verify} loading={busy === 'verify'}>Verify chain</Button>
            <Button onClick={exportBundle} loading={busy === 'export'}>Export signed bundle</Button>
          </>
        }
      />

      {error && <Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert>}
      {verification && (
        <Alert
          tone={verification.ok ? 'success' : 'danger'}
          title={verification.ok ? 'Chain intact' : 'Chain broken'}
          onDismiss={() => setVerification(null)}
        >
          {verification.ok
            ? <>All {formatNumber(verification.verified)} sealed entries verify; head hash <span className="font-mono break-all">{verification.head_hash}</span>.</>
            : <>{formatNumber(verification.verified)} entries verify; the chain breaks at sequence {verification.first_break_seq}{verification.detail ? ` (${verification.detail})` : ''}.</>}
          {' '}{verification.pending > 0 ? `${verification.pending} entries are still waiting to be sealed.` : ''}
        </Alert>
      )}

      <Card as="form" padding="lg" onSubmit={apply} aria-labelledby="filters-h">
        <h2 id="filters-h" className="text-sm font-semibold text-ink mb-3">Filter</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input label="Actor (user id)" value={draft.actor} onChange={set('actor')} />
          <Input label="Action" placeholder="e.g. case_updated" value={draft.action} onChange={set('action')} />
          <Input label="Resource type" placeholder="e.g. case" value={draft.resource_type} onChange={set('resource_type')} />
          <Input label="Resource id" value={draft.resource_id} onChange={set('resource_id')} />
          <Input label="From" type="datetime-local" value={draft.date_from} onChange={set('date_from')} />
          <Input label="To" type="datetime-local" value={draft.date_to} onChange={set('date_to')} />
        </div>
        <div className="flex gap-3 mt-4">
          <Button type="submit">Apply filters</Button>
          <Button variant="ghost" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(0); }}>Clear</Button>
        </div>
      </Card>

      <Card padding="none">
        {log.isLoading && !log.data ? <LoadingState label="Loading audit entries…" /> : log.error ? (
          <div className="p-5"><Alert tone="danger">{errorMessage(log.error)}</Alert></div>
        ) : items.length === 0 ? <EmptyState title="No audit entries match." /> : (
          <Table caption="Audit entries, newest first">
            <THead><Th>Time</Th><Th>Action</Th><Th>Resource</Th><Th>Actor</Th><Th>Seal</Th><Th align="right">Details</Th></THead>
            <TBody>
              {items.map((e) => (
                <Tr key={e.id}>
                  <Td className="text-xs text-ink-muted whitespace-nowrap">{e.created_at ? formatDateTime(e.created_at) : '—'}</Td>
                  <Td className="text-xs font-medium text-ink">{humanize(e.action)}</Td>
                  <Td className="text-xs text-ink-secondary">{e.resource_type ? `${e.resource_type}${e.resource_id ? ` · ${e.resource_id}` : ''}` : '—'}</Td>
                  <Td className="text-xs font-mono text-ink-muted">{e.user_id ?? 'system'}</Td>
                  <Td>{e.sealed ? <Badge tone="success">#{e.seq}</Badge> : <Badge tone="warning">Pending</Badge>}</Td>
                  <Td align="right"><Button variant="ghost" size="sm" onClick={() => setSelected(e)} aria-label={`Details of audit entry ${e.id}`}>View</Button></Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
        {(log.data?.total ?? 0) > 0 && (
          <Pagination label="Audit pages" page={page} pageSize={PAGE_SIZE} total={log.data!.total} onPageChange={setPage} />
        )}
      </Card>

      {selected && (
        <Modal open onClose={() => setSelected(null)} title={humanize(selected.action)} description={selected.id} size="2xl"
          footer={<Button variant="secondary" onClick={() => setSelected(null)}>Close</Button>}>
          <pre className="overflow-x-auto text-xs bg-bg-alt rounded-lg p-3">{JSON.stringify(selected, null, 2)}</pre>
        </Modal>
      )}
      {showKey && <PublicKeyModal onClose={() => setShowKey(false)} />}
    </div>
  );
}

function PublicKeyModal({ onClose }: { onClose: () => void }) {
  const { data, error } = useSWR('audit-public-key', api.auditPublicKey);
  return (
    <Modal open onClose={onClose} title="Export verification key" description="Verify a downloaded bundle offline with backend/scripts/verify_audit_export.py and this key." size="xl"
      footer={<>{data && <CopyButton value={data.public_key} label="Copy key" />}<Button variant="secondary" onClick={onClose}>Close</Button></>}>
      {error ? <Alert tone="danger">{errorMessage(error)}</Alert> : !data ? <LoadingState /> : (
        <>
          <p className="text-xs text-ink-muted mb-2">Algorithm: {data.algorithm}</p>
          <pre className="overflow-x-auto text-xs bg-bg-alt rounded-lg p-3">{data.public_key}</pre>
        </>
      )}
    </Modal>
  );
}

export default function AuditPage() {
  return (
    <PlatformLayout>
      <Audit />
    </PlatformLayout>
  );
}
