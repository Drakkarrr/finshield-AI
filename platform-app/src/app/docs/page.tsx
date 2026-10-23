'use client';

import React, { useState, useEffect } from 'react';
import PlatformLayout from '@/components/PlatformLayout';
import { Card, Badge, Spinner } from '@/components/ui';

interface OpenAPISpec {
  openapi: string;
  info: {
    title: string;
    version: string;
    description?: string;
  };
  paths: Record<string, Record<string, {
    summary?: string;
    description?: string;
    tags?: string[];
    parameters?: any[];
    requestBody?: any;
    responses?: any;
  }>>;
}

export default function DocsPage() {
  const [spec, setSpec] = useState<OpenAPISpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedTag, setSelectedTag] = useState<string>('all');

  useEffect(() => {
    fetch('/api/openapi.json')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load OpenAPI spec');
        return res.json();
      })
      .then(data => {
        setSpec(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <PlatformLayout>
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" />
        </div>
      </PlatformLayout>
    );
  }

  if (error || !spec) {
    return (
      <PlatformLayout>
        <div className="p-6">
          <div className="bg-danger-bg border border-danger-light text-danger p-4 rounded-xl">
            {error || 'Failed to load API documentation'}
          </div>
        </div>
      </PlatformLayout>
    );
  }

  const tags = Array.from(
    new Set(
      Object.values(spec.paths).flatMap((methods) =>
        Object.values(methods).flatMap((endpoint) => endpoint.tags || [])
      )
    )
  ).sort();

  const filteredPaths = Object.entries(spec.paths).filter(([, methods]) =>
    selectedTag === 'all' ||
    Object.values(methods).some((endpoint) => endpoint.tags?.includes(selectedTag))
  );

  return (
    <PlatformLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-ink">{spec.info.title}</h1>
          <p className="text-sm text-ink-muted mt-1">
            Version {spec.info.version} · OpenAPI {spec.openapi}
          </p>
          {spec.info.description && (
            <p className="text-sm text-ink-secondary mt-3">{spec.info.description}</p>
          )}
        </div>

        {/* Tag Filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setSelectedTag('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              selectedTag === 'all'
                ? 'bg-accent/10 text-accent-dark'
                : 'text-ink-muted hover:bg-bg'
            }`}
          >
            All Endpoints
          </button>
          {tags.map((tag) => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedTag === tag
                  ? 'bg-accent/10 text-accent-dark'
                  : 'text-ink-muted hover:bg-bg'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>

        {/* Endpoints */}
        <div className="space-y-4">
          {filteredPaths.map(([path, methods]) => (
            <Card key={path} padding="none">
              <div className="p-4 border-b border-border-light">
                <code className="text-sm font-mono font-semibold text-ink">{path}</code>
              </div>
              <div className="divide-y divide-border-light">
                {Object.entries(methods).map(([method, endpoint]) => (
                  <div key={method} className="p-4">
                    <div className="flex items-start gap-3 mb-2">
                      <Badge
                        variant={
                          method === 'get' ? 'info' :
                          method === 'post' ? 'success' :
                          method === 'put' ? 'warning' :
                          method === 'delete' ? 'danger' : 'neutral'
                        }
                      >
                        {method.toUpperCase()}
                      </Badge>
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-ink">
                          {endpoint.summary || 'Untitled'}
                        </h3>
                        {endpoint.description && (
                          <p className="text-xs text-ink-muted mt-1">{endpoint.description}</p>
                        )}
                      </div>
                    </div>
                    {endpoint.tags && (
                      <div className="flex gap-1 mt-2">
                        {endpoint.tags.map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-2 py-0.5 rounded bg-bg-alt text-ink-muted"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>

        {/* Link to Swagger UI */}
        <div className="pt-4 border-t border-border-light">
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-accent hover:text-accent-dark font-medium"
          >
            View Interactive API Documentation (Swagger UI) →
          </a>
        </div>
      </div>
    </PlatformLayout>
  );
}
