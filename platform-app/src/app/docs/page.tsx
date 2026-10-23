'use client';

import React, { useMemo, useState } from 'react';
import useSWR from 'swr';
import PlatformLayout from '@/components/PlatformLayout';
import { api, errorMessage, OpenAPIOperation } from '@/lib/api';
import {
  Alert, Badge, Card, EmptyState, Input, LoadingState, PageHeader, Select, Table, TBody, THead, Td, Th, Tone, Tr,
} from '@/components/ui';
import { formatNumber } from '@/lib/format';

const METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'];
const METHOD_TONES: Record<string, Tone> = { get: 'info', post: 'success', put: 'warning', patch: 'warning', delete: 'danger' };

interface Operation extends OpenAPIOperation {
  method: string;
  path: string;
}

/**
 * Rendered at runtime from the backend's own OpenAPI document, so this page lists exactly the
 * routes FastAPI exposes — there is no hand-maintained endpoint list to drift.
 */
function Docs() {
  const { data: spec, error, isLoading } = useSWR('openapi', api.openapi);
  const [tag, setTag] = useState('');
  const [q, setQ] = useState('');

  const operations = useMemo<Operation[]>(() => {
    if (!spec) return [];
    return Object.entries(spec.paths).flatMap(([path, item]) =>
      Object.entries(item)
        .filter(([method]) => METHODS.includes(method))
        .map(([method, op]) => ({ ...(op as OpenAPIOperation), method, path })),
    );
  }, [spec]);

  const tags = useMemo(() => Array.from(new Set(operations.flatMap((o) => o.tags ?? ['Untagged']))).sort(), [operations]);
  const needle = q.trim().toLowerCase();
  const shown = operations.filter((o) =>
    (!tag || (o.tags ?? ['Untagged']).includes(tag)) &&
    (!needle || o.path.toLowerCase().includes(needle) || (o.summary ?? '').toLowerCase().includes(needle)),
  );

  if (isLoading) return <LoadingState label="Loading the API schema…" />;
  if (error || !spec) {
    return <Alert tone="danger" title="Could not load /api/openapi.json">{errorMessage(error, 'The backend did not return its OpenAPI document.')}</Alert>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${spec.info.title} API`}
        description={<>Version {spec.info.version} · OpenAPI {spec.openapi} · {formatNumber(operations.length)} operations on {formatNumber(Object.keys(spec.paths).length)} paths, read live from the backend</>}
        actions={<a href="/api/docs" target="_blank" rel="noopener noreferrer" className="text-sm font-medium">Interactive docs (Swagger UI) ↗</a>}
      />

      <div className="flex flex-wrap items-end gap-3">
        <Input label="Search paths and summaries" type="search" value={q} onChange={(e) => setQ(e.target.value)} className="w-72" />
        <Select label="Tag" className="w-48" value={tag} onChange={(e) => setTag(e.target.value)} options={[{ value: '', label: 'All tags' }, ...tags.map((t) => ({ value: t, label: t }))]} />
        <p className="text-xs text-ink-muted pb-3" aria-live="polite">{formatNumber(shown.length)} shown</p>
      </div>

      <Card padding="none">
        {shown.length === 0 ? <EmptyState title="No operations match." /> : (
          <Table caption="API operations">
            <THead><Th>Method</Th><Th>Path</Th><Th>Summary</Th><Th>Tags</Th></THead>
            <TBody>
              {shown.map((o) => (
                <Tr key={`${o.method} ${o.path}`}>
                  <Td><Badge tone={METHOD_TONES[o.method] ?? 'neutral'}>{o.method.toUpperCase()}</Badge></Td>
                  <Td className="font-mono text-xs text-ink">{o.path}{o.deprecated && <span className="ml-2 text-warning-fg">(deprecated)</span>}</Td>
                  <Td className="text-xs text-ink-secondary">
                    {o.summary}
                    {o.description && <span className="block text-2xs text-ink-muted mt-0.5">{o.description.split('\n')[0]}</span>}
                  </Td>
                  <Td className="text-2xs text-ink-muted">{(o.tags ?? []).join(', ')}</Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

export default function DocsPage() {
  return (
    <PlatformLayout>
      <Docs />
    </PlatformLayout>
  );
}
