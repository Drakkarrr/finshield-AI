'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useCan } from '@/contexts/AuthContext';
import { api, errorMessage, RuntimeSetting } from '@/lib/api';
import {
  Alert, Badge, Button, Card, EmptyState, LoadingState, Modal, PageHeader, StatusBadge, Switch, Table, TBody, Textarea,
  THead, Td, Th, Tone, Tr, humanize,
} from '@/components/ui';
import { formatDateTime, formatNumber, timeAgo } from '@/lib/format';

const BREAKER_TONES: Record<string, Tone> = { closed: 'success', half_open: 'warning', open: 'danger' };

function Operations() {
  const can = useCan();
  return (
    <div className="space-y-6">
      <PageHeader title="Operations" description="Dependency health, watch-list freshness and runtime configuration" />
      <Breakers canReset={can(['POST', '/api/v1/health/circuit-breakers/{dependency}/reset'])} />
      <Lists />
      {can(['GET', '/api/v1/flags']) && <Flags canEdit={can(['PUT', '/api/v1/flags/{key}'])} />}
      {can(['GET', '/api/v1/models']) && <Models canPromote={can(['POST', '/api/v1/models/{version_id}/promote'])} />}
      {can(['GET', '/api/v1/settings']) && <Settings canEdit={can(['PUT', '/api/v1/settings/{key}'])} />}
    </div>
  );
}

function Section({ id, title, description, children }: { id: string; title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card as="section" padding="none" aria-labelledby={id}>
      <div className="px-5 pt-5 pb-3">
        <h2 id={id} className="text-sm font-semibold text-ink">{title}</h2>
        {description && <p className="text-xs text-ink-muted mt-0.5">{description}</p>}
      </div>
      {children}
    </Card>
  );
}

function Breakers({ canReset }: { canReset: boolean }) {
  const breakers = useSWR('breakers', api.circuitBreakers, { refreshInterval: 30_000 });
  const [error, setError] = useState('');
  const reset = async (dep: string) => {
    setError('');
    try {
      await api.resetBreaker(dep);
      breakers.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Reset failed.'));
    }
  };
  return (
    <Section id="breakers-h" title="Circuit breakers" description="State of the breaker around each real dependency; refreshed every 30 s while visible. An open breaker routes affected decisions to human review.">
      {error && <div className="px-5 pb-3"><Alert tone="danger">{error}</Alert></div>}
      {breakers.isLoading && !breakers.data ? <LoadingState /> : breakers.error ? (
        <div className="p-5"><Alert tone="danger">{errorMessage(breakers.error)}</Alert></div>
      ) : (
        <Table caption="Circuit breakers">
          <THead><Th>Dependency</Th><Th>State</Th><Th>Failures</Th><Th>Last change</Th>{canReset && <Th align="right">Actions</Th>}</THead>
          <TBody>
            {(breakers.data?.breakers ?? []).map((b) => (
              <Tr key={b.dependency}>
                <Th scope="row">{humanize(b.dependency)}</Th>
                <Td><Badge tone={BREAKER_TONES[b.state] ?? 'neutral'} dot>{humanize(b.state)}</Badge></Td>
                <Td className="text-xs">{b.failure_count}</Td>
                <Td className="text-xs text-ink-muted">{b.last_state_change_at ? timeAgo(b.last_state_change_at) : '—'}</Td>
                {canReset && (
                  <Td align="right">
                    {b.state !== 'closed' && <Button variant="secondary" size="sm" onClick={() => reset(b.dependency)}>Reset</Button>}
                  </Td>
                )}
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
    </Section>
  );
}

function Lists() {
  const { data, error, isLoading } = useSWR('lists-status', api.listsStatus);
  return (
    <Section id="lists-h" title="Sanctions and PEP lists" description={data ? `Sources older than ${data.max_age_hours} h are stale.` : undefined}>
      {isLoading ? <LoadingState /> : error ? <div className="p-5"><Alert tone="danger">{errorMessage(error)}</Alert></div> : data && (
        <>
          {(!data.sanctions_loaded || !data.pep_loaded) && (
            <div className="px-5 pb-3">
              <Alert tone="danger">
                {!data.sanctions_loaded && 'No sanctions list is loaded. '}{!data.pep_loaded && 'No PEP list is loaded.'}
              </Alert>
            </div>
          )}
          {data.sources.length === 0 ? <EmptyState title="No list imports yet." /> : (
            <Table caption="List sources">
              <THead><Th>Source</Th><Th>Type</Th><Th>Version</Th><Th>Entries</Th><Th>Imported</Th><Th>Freshness</Th></THead>
              <TBody>
                {data.sources.map((s) => (
                  <Tr key={s.source}>
                    <Th scope="row">{s.source}{s.is_fixture && <span className="ml-2"><Badge tone="warning">Test fixture</Badge></span>}</Th>
                    <Td className="text-xs">{humanize(s.list_type)}</Td>
                    <Td className="text-xs font-mono">{s.list_version}</Td>
                    <Td className="text-xs">{formatNumber(s.entry_count)}</Td>
                    <Td className="text-xs text-ink-muted">{formatDateTime(s.imported_at)}</Td>
                    <Td><Badge tone={s.stale ? 'danger' : 'success'}>{s.stale ? `Stale (${Math.round(s.age_hours)} h)` : 'Fresh'}</Badge></Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          )}
          <p className="px-5 py-3 text-xs text-ink-muted border-t border-border-light">
            High-risk countries: {data.high_risk_countries.length ? data.high_risk_countries.join(', ') : 'none configured'}
          </p>
        </>
      )}
    </Section>
  );
}

function Flags({ canEdit }: { canEdit: boolean }) {
  const flags = useSWR('flags', api.listFlags);
  const [error, setError] = useState('');
  const toggle = async (key: string, enabled: boolean) => {
    setError('');
    try {
      await api.updateFlag(key, enabled);
      flags.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Could not change the flag.'));
    }
  };
  return (
    <Section id="flags-h" title="Feature flags" description={canEdit ? 'Changes apply immediately and are audit-logged.' : 'Read-only: flags are changed by admins.'}>
      {error && <div className="px-5 pb-3"><Alert tone="danger">{error}</Alert></div>}
      {flags.isLoading ? <LoadingState /> : flags.error ? <div className="p-5"><Alert tone="danger">{errorMessage(flags.error)}</Alert></div> : (
        <ul className="divide-y divide-border-light border-t border-border-light">
          {(flags.data ?? []).map((f) => (
            <li key={f.key} className="px-5 py-3">
              {canEdit ? (
                <Switch label={f.key} description={`${f.description} (${f.source === 'override' ? 'override' : 'default'})`} checked={f.enabled} onChange={(v) => toggle(f.key, v)} />
              ) : (
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-mono text-ink">{f.key}</p>
                    <p className="text-xs text-ink-muted">{f.description}</p>
                  </div>
                  <Badge tone={f.enabled ? 'success' : 'neutral'}>{f.enabled ? 'On' : 'Off'}</Badge>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Models({ canPromote }: { canPromote: boolean }) {
  const models = useSWR('models', api.listModels);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const promote = async (id: string, label: string) => {
    if (!window.confirm(`Make ${label} the active scoring model? The current active version is retired.`)) return;
    setError('');
    setSuccess('');
    try {
      const result = await api.promoteModel(id);
      if ('change_request_id' in result) {
        setSuccess(result.message || 'Model promotion proposed. Awaiting approval.');
      } else {
        models.mutate();
      }
    } catch (e) {
      setError(errorMessage(e, 'Promotion failed.'));
    }
  };
  return (
    <Section id="models-h" title="Risk model versions" description="Shadow versions are scored on every eligible screening but never affect a decision until promoted.">
      {error && <div className="px-5 pb-3"><Alert tone="danger">{error}</Alert></div>}
      {success && <div className="px-5 pb-3"><Alert tone="info">{success}</Alert></div>}
      {models.isLoading ? <LoadingState /> : models.error ? <div className="p-5"><Alert tone="danger">{errorMessage(models.error)}</Alert></div> : (models.data ?? []).length === 0 ? (
        <EmptyState title="No model versions registered." />
      ) : (
        <Table caption="Model versions">
          <THead><Th>Version</Th><Th>Kind</Th><Th>Status</Th><Th>Created</Th><Th>Activated</Th>{canPromote && <Th align="right">Actions</Th>}</THead>
          <TBody>
            {models.data!.map((m) => (
              <Tr key={m.id}>
                <Th scope="row" className="font-mono text-xs">{m.label}</Th>
                <Td className="text-xs">{humanize(m.kind)}</Td>
                <Td><StatusBadge status={m.status} /></Td>
                <Td className="text-xs text-ink-muted">{m.created_at ? formatDateTime(m.created_at) : '—'}</Td>
                <Td className="text-xs text-ink-muted">{m.activated_at ? formatDateTime(m.activated_at) : '—'}</Td>
                {canPromote && (
                  <Td align="right">
                    {m.status === 'shadow' && <Button variant="secondary" size="sm" onClick={() => promote(m.id, m.label)}>Promote</Button>}
                  </Td>
                )}
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
    </Section>
  );
}

function Settings({ canEdit }: { canEdit: boolean }) {
  const settings = useSWR('runtime-settings', api.listSettings);
  const [editing, setEditing] = useState<RuntimeSetting | null>(null);
  return (
    <Section id="settings-h" title="Runtime settings" description="Effective value per key for your organisation. Overrides are validated per key and audit-logged.">
      {settings.isLoading ? <LoadingState /> : settings.error ? <div className="p-5"><Alert tone="danger">{errorMessage(settings.error)}</Alert></div> : (
        <Table caption="Runtime settings">
          <THead><Th>Key</Th><Th>Value</Th><Th>Source</Th>{canEdit && <Th align="right">Actions</Th>}</THead>
          <TBody>
            {(settings.data ?? []).map((s) => (
              <Tr key={s.key}>
                <Th scope="row">
                  <span className="font-mono text-xs">{s.key}</span>
                  <span className="block text-2xs text-ink-muted font-normal">{s.description}</span>
                </Th>
                <Td className="font-mono text-xs text-ink-secondary max-w-xs truncate" >{JSON.stringify(s.value)}</Td>
                <Td><Badge tone={s.source === 'override' ? 'accent' : 'neutral'}>{humanize(s.source)}</Badge></Td>
                {canEdit && <Td align="right"><Button variant="ghost" size="sm" onClick={() => setEditing(s)} aria-label={`Edit setting ${s.key}`}>Edit</Button></Td>}
              </Tr>
            ))}
          </TBody>
        </Table>
      )}
      {editing && <EditSettingModal setting={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); settings.mutate(); }} />}
    </Section>
  );
}

function EditSettingModal({ setting, onClose, onSaved }: { setting: RuntimeSetting; onClose: () => void; onSaved: () => void }) {
  const [text, setText] = useState(JSON.stringify(setting.value, null, 2));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    let value: unknown;
    try { value = JSON.parse(text); } catch { setError('The value must be valid JSON (strings in double quotes).'); return; }
    setSaving(true);
    setError('');
    try {
      await api.updateSetting(setting.key, value);
      onSaved();
    } catch (err) {
      setError(errorMessage(err, 'The backend rejected this value.'));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={setting.key} description={setting.description} size="xl">
      <form onSubmit={save} className="space-y-3">
        <Textarea label="Value (JSON)" rows={8} className="font-mono" value={text} onChange={(e) => setText(e.target.value)} helpText={`Default: ${JSON.stringify(setting.default)}`} />
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={() => setText(JSON.stringify(setting.default, null, 2))}>Use default</Button>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Save</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function OperationsPage() {
  return (
    <PlatformLayout>
      <Operations />
    </PlatformLayout>
  );
}
