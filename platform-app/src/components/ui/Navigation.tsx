'use client';

import React, { useRef, useState } from 'react';
import { formatNumber } from '@/lib/format';
import Button from './Button';

// ── Tabs (WAI-ARIA tabs pattern: arrow keys move between tabs) ──
export interface TabItem { id: string; label: string }

export function Tabs({ tabs, value, onChange, label, idPrefix }: {
  tabs: TabItem[]; value: string; onChange: (id: string) => void; label: string; idPrefix: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const move = (delta: number) => {
    const i = tabs.findIndex((t) => t.id === value);
    const next = tabs[(i + delta + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1 bg-bg-alt rounded-xl p-1 w-fit">
      {tabs.map((t) => {
        const selected = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => { refs.current[t.id] = el; }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.id}`}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${t.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight') { e.preventDefault(); move(1); }
              if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1); }
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selected ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ idPrefix, id, children }: { idPrefix: string; id: string; children: React.ReactNode }) {
  return (
    <div role="tabpanel" id={`${idPrefix}-panel-${id}`} aria-labelledby={`${idPrefix}-tab-${id}`} tabIndex={0}>
      {children}
    </div>
  );
}

// ── Filter chips (a group of toggle buttons) ──
export function FilterChips<T extends string>({ label, options, value, onChange }: {
  label: string; options: ReadonlyArray<{ value: T; label: string }>; value: T; onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            o.value === value ? 'bg-accent/15 text-accent-fg' : 'text-ink-muted hover:bg-bg-alt'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Pagination (offset/limit; total from the API) ──
export function Pagination({ page, pageSize, total, onPageChange, label = 'Pagination' }: {
  page: number; pageSize: number; total: number; onPageChange: (page: number) => void; label?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);
  return (
    <nav aria-label={label} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-t border-border-light">
      <p className="text-xs text-ink-muted" aria-live="polite">
        {formatNumber(from)}–{formatNumber(to)} of {formatNumber(total)}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => onPageChange(page - 1)} disabled={page === 0}>
          Previous
        </Button>
        <span className="text-xs text-ink-muted">Page {formatNumber(page + 1)} of {formatNumber(pages)}</span>
        <Button variant="secondary" size="sm" onClick={() => onPageChange(page + 1)} disabled={page + 1 >= pages}>
          Next
        </Button>
      </div>
    </nav>
  );
}

// ── Copy to clipboard ──
export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="primary"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
    >
      <span aria-live="polite">{copied ? 'Copied' : label}</span>
    </Button>
  );
}
