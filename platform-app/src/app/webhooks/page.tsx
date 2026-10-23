'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useCan } from '@/contexts/AuthContext';
import { api, CreatedWebhookSubscription, errorMessage, WebhookEvent } from '@/lib/api';
import {
  Alert, Button, Card, CopyButton, EmptyState, Input, LoadingState, Modal, PageHeader, Pagination, Select, StatusBadge,
  Table, TBody, THead, Td, Th, Tr, humanize,
} from '@/components/ui';
import { formatDateTime, timeAgo } from '@/lib/format';

// backend/app/domain/webhooks.py EVENT_TYPES
const EVENT_TYPES = ['transaction.flagged', 'transaction.blocked', 'case.created', 'case.updated', 'case.resolved', 'filing.submitted', 'sla.breached'];
const DELIVERY_STATUSES = ['pending', 'delivered', 'failed', 'dead_letter'];
const PAGE_SIZE = 25;

function Webhooks() {
  const can = useCan();
  return (
    <div className="space-y-6">
      <PageHeader title="Webhooks" description="Signed event deliveries to your endpoints, with retries and a dead-letter queue" />
      {can(['GET', '/api/v1/webhooks/subscriptions']) && <Subscriptions />}
      <DeliveryLog canRetry={can(['POST', '/api/v1/webhooks/{event_id}/retry'])} />
    </div>
  );
}

function Subscriptions() {
  const subs = useSWR('webhook-subscriptions', api.listWebhookSubscriptions);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CreatedWebhookSubscription | null>(null);
  const [error, setError] = useState('');

  const remove = async (id: string, url: string) => {
    if (!window.confirm(`Stop delivering events to ${url}?`)) return;
    try {
      await api.deleteWebhookSubscription(id);
      subs.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Could not remove the subscription.'));
    }
  };

  const list = subs.data ?? [];
  return (
    <Card as="section" padding="none" aria-labelledby="subs-h">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 pb-3">
        <h2 id="subs-h" className="text-sm font-semibold text-ink">Subscriptions</h2>
        <Button size="sm" onClick={() => setCreating(true)}>Add endpoint</Button>
      </div>
      <div className="px-5 space-y-3">
        {error && <Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert>}
        {created && (
          <Alert tone="warning" title="Copy the signing secret now — it is shown only once" onDismiss={() => setCreated(null)}>
            <p className="mb-2">Use it to verify the signature header on every delivery to <span className="font-mono">{created.url}</span>. It is stored encrypted and cannot be shown again.</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-surface rounded-lg px-3 py-2 text-xs text-ink font-mono break-all">{created.secret}</code>
              <CopyButton value={created.secret} label="Copy secret" />
            </div>
          </Alert>
        )}
      </div>
      {subs.isLoading && !subs.data ? <LoadingState label="Loading subscriptions…" /> : subs.error ? (
        <div className="p-5"><Alert tone="danger">{errorMessage(subs.error)}</Alert></div>
      ) : list.length === 0 ? <EmptyState title="No endpoints subscribed." /> : (
        <Table caption="Webhook subscriptions">
          <THead><Th>Endpoint</Th><Th>Events</Th><Th>Status</Th><Th>Created</Th><Th align="right">Actions</Th></THead>
          <TBody>
            {list.map((s) => (
              <Tr key={s.id}>
                <Th scope="row" className="font-mono text-xs break-all">{s.url}</Th>
                <Td className="text-xs text-ink-secondary">{s.events.includes('*') ? 'All events' : s.events.join(', ')}</Td>
                <Td><StatusBadge status={s.active ? 'active' : 'revoked'} label={s.active ? 'Active' : 'Removed'} /></Td>
                <Td className="text-xs text-ink-muted">{s.created_at ? formatDateTime(s.created_at) : '—'}</Td>
                <Td align="right">
                  {s.active && <Button variant="danger" size="sm" onClick={() => remove(s.id, s.url)} aria-label={`Remove subscription ${s.url}`}>Remove</Button>}
                </Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
      {creating && (
        <CreateSubscriptionModal
          onClose={() => setCreating(false)}
          onCreated={(s) => { setCreating(false); setCreated(s); subs.mutate(); }}
        />
      )}
    </Card>
  );
}

function CreateSubscriptionModal({ onClose, onCreated }: { onClose: () => void; onCreated: (s: CreatedWebhookSubscription) => void }) {
  const [url, setUrl] = useState('');
  const [all, setAll] = useState(true);
  const [events, setEvents] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!all && events.length === 0) { setError('Pick at least one event type.'); return; }
    setSaving(true);
    setError('');
    try {
      onCreated(await api.createWebhookSubscription(url, all ? ['*'] : events));
    } catch (err) {
      setError(errorMessage(err, 'Could not create the subscription.'));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Add webhook endpoint" description="Events are POSTed as signed JSON. Private and internal addresses are refused.">
      <form onSubmit={submit} className="space-y-4">
        <Input label="Endpoint URL" type="url" placeholder="https://example.com/finshield/webhook" value={url} onChange={(e) => setUrl(e.target.value)} required />
        <fieldset>
          <legend className="text-xs font-medium text-ink-secondary mb-2">Events</legend>
          <label className="flex items-center gap-2 text-sm text-ink-secondary mb-2">
            <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} className="w-4 h-4 accent-accent" />
            All events, including types added later
          </label>
          {!all && (
            <div className="grid grid-cols-2 gap-2">
              {EVENT_TYPES.map((t) => (
                <label key={t} className="flex items-center gap-2 text-sm text-ink-secondary">
                  <input
                    type="checkbox"
                    checked={events.includes(t)}
                    onChange={(e) => setEvents(e.target.checked ? [...events, t] : events.filter((x) => x !== t))}
                    className="w-4 h-4 accent-accent"
                  />
                  <span className="font-mono text-xs">{t}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Create subscription</Button>
        </div>
      </form>
    </Modal>
  );
}

function DeliveryLog({ canRetry }: { canRetry: boolean }) {
  const [status, setStatus] = useState('');
  const [eventType, setEventType] = useState('');
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<WebhookEvent | null>(null);
  const [error, setError] = useState('');
  const log = useSWR(['webhook-events', status, eventType, page], () =>
    api.listWebhookEvents({ status: status || undefined, event_type: eventType || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }));

  const retry = async (ev: WebhookEvent) => {
    setError('');
    try {
      await api.retryWebhookEvent(ev.id);
      setSelected(null);
      log.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Retry failed.'));
    }
  };

  const items = log.data?.items ?? [];
  return (
    <Card as="section" padding="none" aria-labelledby="log-h">
      <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-5 pb-3">
        <h2 id="log-h" className="text-sm font-semibold text-ink">Delivery log</h2>
        <div className="flex flex-wrap gap-3">
          <Select label="Delivery status" className="w-44" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}
            options={[{ value: '', label: 'All' }, ...DELIVERY_STATUSES.map((s) => ({ value: s, label: humanize(s) }))]} />
          <Select label="Event type" className="w-52" value={eventType} onChange={(e) => { setEventType(e.target.value); setPage(0); }}
            options={[{ value: '', label: 'All' }, ...EVENT_TYPES.map((t) => ({ value: t, label: t }))]} />
        </div>
      </div>
      {error && <div className="px-5 pb-3"><Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert></div>}
      {log.isLoading && !log.data ? <LoadingState label="Loading deliveries…" /> : log.error ? (
        <div className="p-5"><Alert tone="danger">{errorMessage(log.error)}</Alert></div>
      ) : items.length === 0 ? <EmptyState title="No deliveries match." /> : (
        <Table caption="Webhook deliveries, newest first">
          <THead><Th>Event</Th><Th>Status</Th><Th>Attempts</Th><Th>Response</Th><Th>Created</Th><Th align="right">Actions</Th></THead>
          <TBody>
            {items.map((ev) => (
              <Tr key={ev.id}>
                <Td className="font-mono text-xs">{ev.event_type}</Td>
                <Td><StatusBadge status={ev.status} /></Td>
                <Td className="text-xs">{ev.attempts}</Td>
                <Td className="text-xs text-ink-muted">{ev.response_code ?? (ev.last_error ? 'Error' : '—')}</Td>
                <Td className="text-xs text-ink-muted"><time dateTime={ev.created_at ?? undefined}>{ev.created_at ? timeAgo(ev.created_at) : '—'}</time></Td>
                <Td align="right">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => setSelected(ev)} aria-label={`Details of delivery ${ev.id}`}>Details</Button>
                    {canRetry && ['failed', 'dead_letter'].includes(ev.status) && (
                      <Button variant="secondary" size="sm" onClick={() => retry(ev)} aria-label={`Retry delivery ${ev.id}`}>Retry</Button>
                    )}
                  </div>
                </Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
      {(log.data?.total ?? 0) > 0 && (
        <Pagination label="Delivery log pages" page={page} pageSize={PAGE_SIZE} total={log.data!.total} onPageChange={setPage} />
      )}
      {selected && (
        <Modal open onClose={() => setSelected(null)} title={selected.event_type} description={selected.id} size="2xl"
          footer={
            <>
              {canRetry && ['failed', 'dead_letter'].includes(selected.status) && <Button onClick={() => retry(selected)}>Retry now</Button>}
              <Button variant="secondary" onClick={() => setSelected(null)}>Close</Button>
            </>
          }
        >
          <div className="space-y-3 text-sm">
            <p><StatusBadge status={selected.status} /> · {selected.attempts} attempt(s)
              {selected.next_retry_at && <> · next retry {formatDateTime(selected.next_retry_at)}</>}
              {selected.delivered_at && <> · delivered {formatDateTime(selected.delivered_at)}</>}
            </p>
            {selected.last_error && <Alert tone="danger" title="Last error">{selected.last_error}</Alert>}
            <h3 className="text-sm font-semibold text-ink">Payload</h3>
            <pre className="overflow-x-auto text-xs bg-bg-alt rounded-lg p-3">{JSON.stringify(selected.payload, null, 2)}</pre>
            <h3 className="text-sm font-semibold text-ink">Attempt log</h3>
            <pre className="overflow-x-auto text-xs bg-bg-alt rounded-lg p-3">{JSON.stringify(selected.attempt_log, null, 2)}</pre>
          </div>
        </Modal>
      )}
    </Card>
  );
}

export default function WebhooksPage() {
  return (
    <PlatformLayout>
      <Webhooks />
    </PlatformLayout>
  );
}
