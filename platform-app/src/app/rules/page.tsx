'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { api, RuleDefinition } from '@/lib/api';

const ACTION_COLORS: Record<string, string> = {
  block: 'text-red-600 bg-red-50',
  flag: 'text-amber-600 bg-amber-50',
  review: 'text-blue-600 bg-blue-50',
  escalate: 'text-orange-600 bg-orange-50',
};

export default function RulesPage() {
  const [rules, setRules] = useState<RuleDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState<string | null>(null);
  const [editRule, setEditRule] = useState<RuleDefinition | null>(null);

  const loadRules = useCallback(async () => {
    try {
      const data = await api.listRules();
      setRules(data);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load rules.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRules(); }, [loadRules]);

  const handleToggle = async (rule: RuleDefinition) => {
    setToggling(rule.rule_id);
    try {
      await api.updateRule(rule.rule_id, { enabled: !rule.enabled });
      setRules(rules.map(r => r.rule_id === rule.rule_id ? { ...r, enabled: !r.enabled, is_customized: true } : r));
    } catch (e: any) {
      setError(e.message || 'Failed to toggle rule.');
    } finally {
      setToggling(null);
    }
  };

  const handleSaveEdit = async (params: Record<string, unknown>) => {
    if (!editRule) return;
    try {
      await api.updateRule(editRule.rule_id, { custom_parameters: params });
      await loadRules();
      setEditRule(null);
    } catch (e: any) {
      setError(e.message || 'Failed to update rule parameters.');
    }
  };

  return (
    <PlatformLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">Compliance Rules</h1>
            <p className="text-sm text-ink-muted mt-0.5">Configure and manage hard rules evaluated before the ML pipeline</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-light">{rules.filter(r => r.enabled).length}/{rules.length} active</span>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="glass p-12 text-center">
            <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-ink-muted">Loading rules...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {rules.map((r) => (
              <div key={r.rule_id} className={`glass p-5 transition-all ${!r.enabled ? 'opacity-60' : ''}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-ink-light">{r.rule_id}</span>
                    <span className="text-sm font-semibold text-ink">{r.name}</span>
                    {r.is_customized && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold text-accent-dark bg-accent/10">CUSTOMIZED</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${ACTION_COLORS[r.action] || 'text-ink-muted bg-gray-100'}`}>
                      {r.action.toUpperCase()}
                    </span>
                    {/* Toggle */}
                    <button
                      onClick={() => handleToggle(r)}
                      disabled={toggling === r.rule_id}
                      className={`relative w-9 h-5 rounded-full transition-colors ${r.enabled ? 'bg-accent/30' : 'bg-white/10'} disabled:opacity-50`}
                    >
                      <span className={`absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-all ${r.enabled ? 'translate-x-4 bg-accent' : 'bg-gray-400'}`} />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-ink-muted mb-3">{r.description}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 text-xs text-ink-light">
                    <span>Type: <span className="text-ink-secondary capitalize">{r.rule_type}</span></span>
                    {Object.entries(r.parameters).map(([k, v]) => (
                      <span key={k}>{k}: <span className="font-mono text-ink-secondary">{Array.isArray(v) ? v.join(', ') : String(v)}</span></span>
                    ))}
                    {r.metadata?.list_size != null && (
                      <span className="text-ink-light">list size: <span className="font-mono text-ink-secondary">{r.metadata.list_size}</span> <span className="text-ink-light/70">(managed)</span></span>
                    )}
                  </div>
                  {r.metadata?.editable ? (
                    <button
                      onClick={() => setEditRule(r)}
                      className="text-xs text-accent-dark hover:text-accent-dark transition-colors"
                    >
                      Edit parameters
                    </button>
                  ) : (
                    <span className="text-[10px] text-ink-light italic">List managed by FinShield</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Edit Modal */}
        {editRule && (
          <EditRuleModal rule={editRule} onClose={() => setEditRule(null)} onSave={handleSaveEdit} />
        )}

        <div className="glass p-5">
          <p className="text-xs text-ink-light">
            Rules are evaluated in the Rule Engine stage (stage 3) of the 7-stage pipeline. A triggered rule
            short-circuits to a decision without invoking the ML stack, keeping cost and latency low.
            Toggle rules on/off or customize parameters to fit your compliance requirements.
          </p>
        </div>
      </div>
    </PlatformLayout>
  );
}

// ── Edit Rule Modal ──
function EditRuleModal({ rule, onClose, onSave }: { rule: RuleDefinition; onClose: () => void; onSave: (params: Record<string, unknown>) => void }) {
  const [params, setParams] = useState<Record<string, string>>(() => {
    const p: Record<string, string> = {};
    Object.entries(rule.parameters).forEach(([k, v]) => {
      p[k] = Array.isArray(v) ? v.join(', ') : String(v);
    });
    return p;
  });

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-md glass border border-border rounded-2xl shadow-2xl p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-ink mb-1">Edit Rule Parameters</h3>
        <p className="text-xs text-ink-muted mb-4">{rule.rule_id} — {rule.name}</p>

        <div className="space-y-3">
          {Object.entries(params).map(([key, value]) => (
            <div key={key}>
              <label className="block text-xs font-medium text-ink-muted mb-1 capitalize">{key.replace(/_/g, ' ')}</label>
              <input
                value={value}
                onChange={e => setParams({ ...params, [key]: e.target.value })}
                className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light"
              />
            </div>
          ))}
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-ink-muted hover:text-ink transition-colors">Cancel</button>
          <button
            onClick={() => {
              const parsed: Record<string, unknown> = {};
              Object.entries(params).forEach(([k, v]) => {
                // Try to parse as number or array
                const num = Number(v);
                if (!isNaN(num) && v.trim() !== '') {
                  parsed[k] = num;
                } else if (v.includes(',')) {
                  parsed[k] = v.split(',').map(s => s.trim());
                } else {
                  parsed[k] = v;
                }
              });
              onSave(parsed);
            }}
            className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-6 py-2 rounded-xl transition-all"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
