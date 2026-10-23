import React from 'react';

// ── Card ──
const paddings = { none: '', sm: 'p-4', md: 'p-5', lg: 'p-6' } as const;

interface CardProps extends React.HTMLAttributes<HTMLElement> {
  padding?: keyof typeof paddings;
  as?: 'div' | 'section' | 'article' | 'form';
}

export function Card({ padding = 'md', as: Tag = 'div', className = '', children, ...props }: CardProps) {
  return (
    <Tag className={`glass ${paddings[padding]} ${className}`} {...props}>
      {children}
    </Tag>
  );
}

// ── Badge ──
export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'accent';

const tones: Record<Tone, string> = {
  success: 'bg-success-bg text-success-fg border-success-light',
  warning: 'bg-warning-bg text-warning-fg border-warning-light',
  danger: 'bg-danger-bg text-danger-fg border-danger-light',
  info: 'bg-info-bg text-info-fg border-info-light',
  neutral: 'bg-bg-alt text-ink-secondary border-border',
  accent: 'bg-accent/10 text-accent-fg border-accent/20',
};

export function Badge({ tone = 'neutral', dot = false, className = '', children }: {
  tone?: Tone; dot?: boolean; className?: string; children: React.ReactNode;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-2xs font-semibold border whitespace-nowrap ${tones[tone]} ${className}`}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden="true" />}
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, Tone> = {
  approved: 'success', resolved: 'success', closed: 'success', confirmed: 'success', delivered: 'success',
  completed: 'success', active: 'success',
  flagged: 'warning', under_review: 'warning', in_review: 'warning', pending: 'warning', submitted: 'info',
  received: 'info', created: 'info', open: 'info', shadow: 'info', draft: 'neutral', retired: 'neutral', revoked: 'neutral',
  blocked: 'danger', escalated: 'danger', rejected: 'danger', failed: 'danger', dead_letter: 'danger',
};

export function humanize(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Status pill: the text label always carries the meaning; colour only reinforces it. */
export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <Badge tone={STATUS_TONES[status] ?? 'neutral'} dot>{label ?? humanize(status)}</Badge>;
}

// ── Alert ──
const alertRoles: Record<Tone, 'alert' | 'status'> = {
  danger: 'alert', warning: 'status', success: 'status', info: 'status', neutral: 'status', accent: 'status',
};

export function Alert({ tone = 'info', title, onDismiss, className = '', children }: {
  tone?: Tone; title?: string; onDismiss?: () => void; className?: string; children?: React.ReactNode;
}) {
  return (
    <div role={alertRoles[tone]} className={`p-4 rounded-xl border text-sm ${tones[tone]} ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {title && <p className="font-semibold mb-0.5">{title}</p>}
          {children}
        </div>
        {onDismiss && (
          <button type="button" onClick={onDismiss} className="opacity-70 hover:opacity-100" aria-label="Dismiss message">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

// ── Spinner / loading / empty ──
const spinnerSizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-10 h-10' } as const;

export function Spinner({ size = 'md', className = '' }: { size?: keyof typeof spinnerSizes; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block ${spinnerSizes[size]} border-2 border-accent/30 border-t-accent rounded-full animate-spin ${className}`}
    />
  );
}

export function LoadingState({ label = 'Loading…', className = '' }: { label?: string; className?: string }) {
  return (
    <div role="status" className={`py-12 text-center ${className}`}>
      <Spinner className="mx-auto mb-3" />
      <p className="text-sm text-ink-muted">{label}</p>
    </div>
  );
}

export function EmptyState({ title, description, action }: {
  title: string; description?: string; action?: React.ReactNode;
}) {
  return (
    <div className="py-12 px-6 text-center">
      <p className="text-sm font-medium text-ink-secondary">{title}</p>
      {description && <p className="text-sm text-ink-muted mt-1">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Page header ──
export function PageHeader({ title, description, actions }: {
  title: string; description?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
        {description && <p className="text-sm text-ink-muted mt-0.5">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

// ── Meter ──
const meterTones: Record<Tone, string> = {
  success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger', info: 'bg-info',
  neutral: 'bg-ink-muted', accent: 'bg-accent',
};

/**
 * A bar whose value is exposed as text (aria-valuetext + an optional visible label), so the
 * meaning never depends on colour or bar length alone.
 */
export function Meter({ value, max = 100, label, valueText, tone = 'accent', showValue = false, className = '' }: {
  value: number; max?: number; label: string; valueText?: string; tone?: Tone; showValue?: boolean; className?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const text = valueText ?? `${Math.round(pct)}%`;
  return (
    <div className={className}>
      {showValue && (
        <div className="flex items-center justify-between text-2xs text-ink-muted mb-1">
          <span>{label}</span>
          <span className="font-semibold text-ink-secondary">{text}</span>
        </div>
      )}
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={text}
        className="w-full h-1.5 bg-bg-alt rounded-full overflow-hidden"
      >
        {/* width is data, not styling: the one inline style the design rules allow */}
        <div className={`h-full rounded-full transition-all ${meterTones[tone]}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Key/value ──
export function InfoRow({ label, value, full = false }: { label: string; value: React.ReactNode; full?: boolean }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <dt className="text-2xs text-ink-muted uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-ink font-medium mt-0.5 break-words">{value}</dd>
    </div>
  );
}
