import React, { useId } from 'react';

const control =
  'w-full bg-surface border rounded-xl px-4 py-2.5 text-sm text-ink placeholder:text-ink-light transition-colors ' +
  'focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 ' +
  'disabled:bg-bg-alt disabled:text-ink-muted read-only:bg-bg-alt';

interface FieldProps {
  /** Every control has a visible label; `hideLabel` keeps it for screen readers only. */
  label: string;
  hideLabel?: boolean;
  error?: string;
  helpText?: string;
}

function useField(id: string | undefined, error?: string, helpText?: string) {
  const generated = useId();
  const controlId = id || generated;
  const describedBy = error ? `${controlId}-error` : helpText ? `${controlId}-help` : undefined;
  return { controlId, describedBy };
}

function Label({ htmlFor, label, hide }: { htmlFor: string; label: string; hide?: boolean }) {
  return (
    <label htmlFor={htmlFor} className={hide ? 'sr-only' : 'block text-xs font-medium text-ink-secondary mb-1'}>
      {label}
    </label>
  );
}

function Hint({ id, error, helpText }: { id: string; error?: string; helpText?: string }) {
  if (error) return <p id={`${id}-error`} className="mt-1 text-xs text-danger-fg">{error}</p>;
  if (helpText) return <p id={`${id}-help`} className="mt-1 text-xs text-ink-muted">{helpText}</p>;
  return null;
}

type InputProps = FieldProps & React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ label, hideLabel, error, helpText, id, className = '', ...props }: InputProps) {
  const { controlId, describedBy } = useField(id, error, helpText);
  return (
    <div className={className}>
      <Label htmlFor={controlId} label={label} hide={hideLabel} />
      <input
        id={controlId}
        className={`${control} ${error ? 'border-danger' : 'border-border'}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      <Hint id={controlId} error={error} helpText={helpText} />
    </div>
  );
}

type TextareaProps = FieldProps & React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ label, hideLabel, error, helpText, id, className = '', ...props }: TextareaProps) {
  const { controlId, describedBy } = useField(id, error, helpText);
  return (
    <div className={className}>
      <Label htmlFor={controlId} label={label} hide={hideLabel} />
      <textarea
        id={controlId}
        className={`${control} ${error ? 'border-danger' : 'border-border'}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      <Hint id={controlId} error={error} helpText={helpText} />
    </div>
  );
}

type SelectProps = FieldProps &
  React.SelectHTMLAttributes<HTMLSelectElement> & { options: ReadonlyArray<{ value: string; label: string }> };

export function Select({ label, hideLabel, error, helpText, options, id, className = '', ...props }: SelectProps) {
  const { controlId, describedBy } = useField(id, error, helpText);
  return (
    <div className={className}>
      <Label htmlFor={controlId} label={label} hide={hideLabel} />
      <select
        id={controlId}
        className={`${control} ${error ? 'border-danger' : 'border-border'}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <Hint id={controlId} error={error} helpText={helpText} />
    </div>
  );
}

interface SwitchProps {
  label: string;
  hideLabel?: boolean;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  description?: string;
}

/** An on/off toggle: `role="switch"` with the state announced, not conveyed by colour alone. */
export function Switch({ label, hideLabel, checked, onChange, disabled, description }: SwitchProps) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-4">
      <div className={hideLabel ? 'sr-only' : ''}>
        <span id={`${id}-label`} className="block text-sm text-ink-secondary">{label}</span>
        {description && <span id={`${id}-desc`} className="block text-xs text-ink-muted">{description}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${
          checked ? 'bg-accent border-accent' : 'bg-bg-alt border-border-dark'
        }`}
      >
        <span
          aria-hidden="true"
          className={`inline-block h-4 w-4 rounded-full bg-surface shadow-card transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'}`}
        />
      </button>
    </div>
  );
}
