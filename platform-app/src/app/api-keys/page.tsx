'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { api, ApiKeyData, errorMessage } from '@/lib/api';
import {
  Alert, Button, Card, CopyButton, EmptyState, Input, LoadingState, PageHeader, StatusBadge, Table, TBody, THead, Td, Th, Tr,
} from '@/components/ui';
import { formatDate } from '@/lib/format';

function ApiKeys() {
  const keys = useSWR('api-keys', api.listApiKeys);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState<ApiKeyData | null>(null);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      setCreated(await api.createApiKey(name));
      setName('');
      keys.mutate();
    } catch (err) {
      setError(errorMessage(err, 'Failed to create key.'));
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (k: ApiKeyData) => {
    if (!window.confirm(`Revoke the key “${k.name}”? Clients using it stop working immediately.`)) return;
    try {
      await api.revokeApiKey(k.id);
      keys.mutate();
    } catch (err) {
      setError(errorMessage(err, 'Failed to revoke key.'));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="API keys" description="Credentials for programmatic access (sent as a Bearer token)" />
      {error && <Alert tone="danger" onDismiss={() => setError('')}>{error}</Alert>}

      {created?.key && (
        <Alert tone="warning" title="Copy this key now — it is shown only once" onDismiss={() => setCreated(null)}>
          <div className="flex items-center gap-2 mt-2">
            <code className="flex-1 bg-surface rounded-lg px-3 py-2 text-xs text-ink font-mono break-all">{created.key}</code>
            <CopyButton value={created.key} />
          </div>
        </Alert>
      )}

      <Card as="section" padding="lg" aria-labelledby="new-key-h">
        <h2 id="new-key-h" className="text-sm font-semibold text-ink mb-4">Create a key</h2>
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <Input label="Key name" placeholder="e.g. Production, Staging" value={name} onChange={(e) => setName(e.target.value)} required className="flex-1 min-w-60" />
          <Button type="submit" loading={creating}>Generate key</Button>
        </form>
      </Card>

      <Card padding="none">
        {keys.isLoading && !keys.data ? <LoadingState label="Loading keys…" /> : keys.error ? (
          <div className="p-5"><Alert tone="danger">{errorMessage(keys.error)}</Alert></div>
        ) : (keys.data ?? []).length === 0 ? (
          <EmptyState title="No API keys yet." description="Create one to screen transactions programmatically." />
        ) : (
          <Table caption="API keys">
            <THead><Th>Name</Th><Th>Key</Th><Th>Status</Th><Th>Created</Th><Th>Last used</Th><Th align="right">Actions</Th></THead>
            <TBody>
              {keys.data!.map((k) => (
                <Tr key={k.id}>
                  <Th scope="row">{k.name}</Th>
                  <Td className="font-mono text-xs text-ink-muted">{k.key_prefix}••••••••</Td>
                  <Td><StatusBadge status={k.is_active ? 'active' : 'revoked'} label={k.is_active ? 'Active' : 'Revoked'} /></Td>
                  <Td className="text-xs text-ink-muted">{formatDate(k.created_at)}</Td>
                  <Td className="text-xs text-ink-muted">{k.last_used_at ? formatDate(k.last_used_at) : 'Never'}</Td>
                  <Td align="right">
                    {k.is_active && <Button variant="danger" size="sm" onClick={() => revoke(k)} aria-label={`Revoke key ${k.name}`}>Revoke</Button>}
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <Card as="section" padding="lg" aria-labelledby="quickstart-h">
        <h2 id="quickstart-h" className="text-sm font-semibold text-ink mb-3">Quick start</h2>
        <p className="text-xs text-ink-muted mb-3">Screen a transaction with your API key:</p>
        <pre className="bg-bg-alt rounded-xl p-4 text-xs text-ink-secondary overflow-x-auto">
{`curl -X POST https://<your-finshield-host>/api/v1/transactions \\
  -H "Authorization: Bearer <your-api-key>" \\
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
      </Card>
    </div>
  );
}

export default function ApiKeysPage() {
  return (
    <PlatformLayout>
      <ApiKeys />
    </PlatformLayout>
  );
}
