'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { useCan } from '@/contexts/AuthContext';
import { api, errorMessage, RuleDefinition, RuleSimulation } from '@/lib/api';
import {
  Alert, Badge, Button, Card, InfoRow, Input, LoadingState, Modal, PageHeader, Switch, Tone, humanize,
} from '@/components/ui';
import { formatDateTime, formatNumber, formatPercent } from '@/lib/format';

const ACTION_TONES: Record<string, Tone> = { block: 'danger', flag: 'warning', review: 'info', escalate: 'danger' };

function Rules() {
  const can = useCan();
  const rules = useSWR('rules', api.listRules);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState<string | null>(null);
  const [editing, setEditing] = useState<RuleDefinition | null>(null);
  const [inspecting, setInspecting] = useState<RuleDefinition | null>(null);
  const canConfigure = can(['PATCH', '/api/v1/rules/{rule_id}']);
  const list = rules.data ?? [];

  const toggle = async (rule: RuleDefinition) => {
    setToggling(rule.rule_id);
    setError('');
    try {
      await api.updateRule(rule.rule_id, { enabled: !rule.enabled });
      await rules.mutate();
    } catch (e) {
      setError(errorMessage(e, 'Failed to change the rule.'));
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compliance rules"
        description="Hard rules evaluated before the scoring stages, in priority order"
        actions={<p className="text-xs text-ink-muted">{list.filter((r) => r.enabled).length} of {list.length} enabled</p>}
      />
      {!canConfigure && list.length > 0 && (
        <Alert tone="info">Rules are configured by admins. You can review them and their hit statistics.</Alert>
      )}
      {error && <Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert>}

      {rules.isLoading && !rules.data ? (
        <Card><LoadingState label="Loading rules…" /></Card>
      ) : rules.error ? (
        <Alert tone="danger" title="Could not load rules">{errorMessage(rules.error)}</Alert>
      ) : (
        <ul className="space-y-3">
          {list.map((r) => (
            <li key={r.rule_id}>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-ink-muted">{r.rule_id}</span>
                    <h2 className="text-sm font-semibold text-ink">{r.name}</h2>
                    <Badge tone={ACTION_TONES[r.action] ?? 'neutral'}>{humanize(r.action)}</Badge>
                    {!r.enabled && <Badge tone="neutral">Disabled</Badge>}
                    {r.is_customized && <Badge tone="accent">Customized</Badge>}
                  </div>
                  {canConfigure && (
                    <Switch label={`Enable ${r.name}`} hideLabel checked={r.enabled} disabled={toggling === r.rule_id} onChange={() => toggle(r)} />
                  )}
                </div>
                <p className="text-sm text-ink-secondary mb-3">{r.description}</p>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                    <span>Type: <span className="text-ink-secondary">{humanize(r.rule_type)}</span></span>
                    {Object.entries(r.parameters).map(([k, v]) => (
                      <span key={k}>{humanize(k)}: <span className="font-mono text-ink-secondary">{Array.isArray(v) ? v.join(', ') : String(v)}</span></span>
                    ))}
                    {r.metadata?.list_size != null && <span>List size: <span className="font-mono text-ink-secondary">{r.metadata.list_size}</span> (managed list)</span>}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setInspecting(r)} aria-label={`Statistics and simulation for ${r.name}`}>
                      Stats{can(['POST', '/api/v1/rules/simulate']) ? ' & simulate' : ''}
                    </Button>
                    {canConfigure && r.metadata?.editable && (
                      <Button variant="secondary" size="sm" onClick={() => setEditing(r)} aria-label={`Edit parameters of ${r.name}`}>Edit parameters</Button>
                    )}
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <EditRuleModal
          rule={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); rules.mutate(); }}
        />
      )}
      {inspecting && <RuleInsightModal rule={inspecting} onClose={() => setInspecting(null)} />}
    </div>
  );
}

function RuleInsightModal({ rule, onClose }: { rule: RuleDefinition; onClose: () => void }) {
  const can = useCan();
  const stats = useSWR(['rule-stats', rule.rule_id], () => api.ruleStats(rule.rule_id));
  const [days, setDays] = useState('30');
  const [sim, setSim] = useState<RuleSimulation | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const simulate = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setError('');
    try {
      setSim(await api.simulateRule(rule.rule_id, Number(days)));
    } catch (err) {
      setError(errorMessage(err, 'Simulation failed.'));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={rule.name} description={rule.rule_id} size="lg" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <div className="space-y-6">
        <section aria-labelledby="stats-h">
          <h3 id="stats-h" className="text-sm font-semibold text-ink mb-2">Hit statistics</h3>
          {stats.isLoading ? <LoadingState label="Loading statistics…" /> : stats.error ? (
            <Alert tone="danger">{errorMessage(stats.error)}</Alert>
          ) : stats.data && (
            <dl className="grid grid-cols-2 gap-3">
              <InfoRow label="Hits" value={formatNumber(stats.data.hit_count)} />
              <InfoRow label="False positives" value={formatNumber(stats.data.false_positive_count)} />
              <InfoRow label="False-positive rate" value={formatPercent(stats.data.false_positive_rate / 100, 1)} />
              <InfoRow label="Last hit" value={stats.data.last_hit_at ? formatDateTime(stats.data.last_hit_at) : 'Never'} />
            </dl>
          )}
        </section>

        {can(['POST', '/api/v1/rules/simulate']) && (
          <section aria-labelledby="sim-h">
            <h3 id="sim-h" className="text-sm font-semibold text-ink mb-2">Simulate against history</h3>
            <form onSubmit={simulate} className="flex items-end gap-3">
              <Input label="Look-back window (days)" type="number" min={1} max={365} value={days} onChange={(e) => setDays(e.target.value)} required className="w-48" />
              <Button type="submit" loading={running}>Run simulation</Button>
            </form>
            {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
            {sim && (
              <dl className="grid grid-cols-2 gap-3 mt-4" aria-live="polite">
                <InfoRow label="Transactions tested" value={formatNumber(sim.transactions_tested)} />
                <InfoRow label="Would trigger" value={`${formatNumber(sim.triggered_count)} (${sim.trigger_rate}%)`} />
                <InfoRow label="Would block" value={formatNumber(sim.would_block)} />
                <InfoRow label="Would flag" value={formatNumber(sim.would_flag)} />
              </dl>
            )}
          </section>
        )}
      </div>
    </Modal>
  );
}

function EditRuleModal({ rule, onClose, onSaved }: { rule: RuleDefinition; onClose: () => void; onSaved: () => void }) {
  const [params, setParams] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(rule.parameters).map(([k, v]) => [k, Array.isArray(v) ? v.join(', ') : String(v)])),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsed: Record<string, unknown> = {};
    Object.entries(params).forEach(([k, v]) => {
      const original = rule.parameters[k];
      if (typeof original === 'number') parsed[k] = Number(v);
      else if (Array.isArray(original)) parsed[k] = v.split(',').map((s) => s.trim()).filter(Boolean);
      else parsed[k] = v;
    });
    setSaving(true);
    setError('');
    try {
      await api.updateRule(rule.rule_id, { custom_parameters: parsed });
      onSaved();
    } catch (err) {
      setError(errorMessage(err, 'Failed to update rule parameters.'));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Edit rule parameters" description={`${rule.rule_id} — ${rule.name}`}>
      <form onSubmit={save} className="space-y-3">
        {Object.entries(params).map(([key, value]) => (
          <Input
            key={key}
            label={humanize(key)}
            type={typeof rule.parameters[key] === 'number' ? 'number' : 'text'}
            step="any"
            value={value}
            helpText={Array.isArray(rule.parameters[key]) ? 'Comma-separated list' : undefined}
            onChange={(e) => setParams({ ...params, [key]: e.target.value })}
          />
        ))}
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Save changes</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function RulesPage() {
  return (
    <PlatformLayout>
      <Rules />
    </PlatformLayout>
  );
}
