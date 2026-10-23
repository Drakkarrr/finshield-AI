import React from 'react';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: Array<{ value: string; label: string }>;
}

export default function Select({
  label,
  error,
  options,
  id,
  className = '',
  ...props
}: SelectProps) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, '_');

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={selectId} className="block text-xs font-medium text-ink-muted mb-1">
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={`w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-all ${
          error ? 'border-danger' : ''
        } ${className}`}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-1 text-xs text-danger">{error}</p>
      )}
    </div>
  );
}
