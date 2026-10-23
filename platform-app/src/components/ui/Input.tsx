import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helpText?: string;
}

export default function Input({
  label,
  error,
  helpText,
  id,
  className = '',
  ...props
}: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '_');

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-ink-muted mb-1">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-light focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/10 transition-all ${
          error ? 'border-danger' : ''
        } ${className}`}
        {...props}
      />
      {error && (
        <p className="mt-1 text-xs text-danger">{error}</p>
      )}
      {helpText && !error && (
        <p className="mt-1 text-xs text-ink-light">{helpText}</p>
      )}
    </div>
  );
}
