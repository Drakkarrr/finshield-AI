'use client';

import React, { useState, useEffect, useCallback } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { api, ApiKeyData } from '@/lib/api';
import { formatDate, formatDateTime } from '@/lib/format';

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState<string | null>(null);
  const [newlyCreated, setNewlyCreated] = useState<ApiKeyData | null>(null);

  const loadKeys = useCallback(async () => {
    try {
      const data = await api.listApiKeys();
      setKeys(data);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Unable to load API keys.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      const created = await api.createApiKey(newName);
      setNewlyCreated(created);
      setNewName('');
      setShowCreate(false);
      await loadKeys();
    } catch (e: any) {
      setError(e.message || 'Failed to create key.');
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await api.revokeApiKey(id);
      setKeys(keys.map(k => k.id === id ? { ...k, is_active: false } : k));
    } catch (e: any) {
      setError(e.message || 'Failed to revoke key.');
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <PlatformLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-ink">API Keys</h1>
            <p className="text-sm text-ink-muted mt-0.5">Manage your API credentials</p>
          </div>
          <button
            onClick={() => { setShowCreate(!showCreate); setNewlyCreated(null); }}
            className="bg-accent hover:bg-accent-light text-ink text-sm font-semibold px-4 py-2.5 rounded-xl transition-all"
          >
            {showCreate ? 'Close' : '+ Create Key'}
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm">{error}</div>
        )}

        {/* Newly created key — shown once */}
        {newlyCreated && newlyCreated.key && (
          <div className="glass p-6 border border-emerald-500/30 animate-fade-in-up">
            <h3 className="text-sm font-semibold text-emerald-600 mb-2">Key created — copy it now</h3>
            <p className="text-xs text-ink-muted mb-3">This is the only time the full key will be shown. Store it securely.</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-bg-alt rounded-lg px-3 py-2 text-xs text-ink font-mono break-all">{newlyCreated.key}</code>
              <button
                onClick={() => handleCopy(newlyCreated.key!)}
                className="shrink-0 text-xs bg-accent hover:bg-accent-light text-ink font-semibold px-3 py-2 rounded-lg transition-all"
              >
                {copied === newlyCreated.key ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>
        )}

        {/* Create Key */}
        {showCreate && (
          <div className="glass p-6 animate-fade-in-up">
            <h3 className="text-sm font-semibold text-ink mb-4">Create New API Key</h3>
            <form onSubmit={handleCreate} className="flex gap-3">
              <input
                placeholder="Key name (e.g. Production, Staging)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="flex-1 bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light"
                required
              />
              <button type="submit" disabled={creating} className="bg-accent hover:bg-accent-light text-ink font-semibold px-6 rounded-xl transition-all disabled:opacity-50">
                {creating ? 'Generating...' : 'Generate'}
              </button>
            </form>
            <p className="text-xs text-ink-light mt-2">Your API key will only be shown once. Copy it immediately.</p>
          </div>
        )}

        {/* Keys List */}
        {loading ? (
          <div className="glass p-12 text-center">
            <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-ink-muted">Loading keys...</p>
          </div>
        ) : keys.length === 0 ? (
          <div className="glass p-12 text-center">
            <p className="text-sm text-ink-light mb-4">No API keys yet. Create one to start screening transactions programmatically.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {keys.map((k) => (
              <div key={k.id} className="glass glass-hover p-5 transition-all duration-300">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-2.5 h-2.5 rounded-full ${k.is_active ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                    <span className="text-sm font-semibold text-ink">{k.name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${k.is_active ? 'text-emerald-600 bg-emerald-50' : 'text-ink-muted bg-gray-100'}`}>
                      {k.is_active ? 'ACTIVE' : 'REVOKED'}
                    </span>
                  </div>
                  {k.is_active && (
                    <button
                      onClick={() => handleRevoke(k.id)}
                      className="text-xs text-red-600 hover:text-red-300 transition-colors px-2 py-1 rounded bg-red-50 hover:bg-red-50"
                    >
                      Revoke
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-ink-light">
                  <span className="font-mono text-ink-muted">{k.key_prefix}••••••••</span>
                  <span>Created: {formatDate(k.created_at)}</span>
                  <span>Last used: {k.last_used_at ? formatDate(k.last_used_at) : 'Never'}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Quick Start */}
        <div className="glass p-6">
          <h3 className="text-sm font-semibold text-ink mb-3">Quick Start</h3>
          <p className="text-xs text-ink-muted mb-3">Screen a transaction with your API key:</p>
          <pre className="bg-bg-alt rounded-xl p-4 text-xs text-ink-secondary overflow-x-auto">
{`curl -X POST http://localhost:8091/api/v1/transactions \\
  -H "Authorization: Bearer <your-jwt-or-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 50000,
    "currency": "USD",
    "transaction_type": "wire",
    "sender_name": "John Doe",
    "receiver_name": "Jane Smith",
    "destination_country": "US"
  }'`}
          </pre>
        </div>
      </div>
    </PlatformLayout>
  );
}
