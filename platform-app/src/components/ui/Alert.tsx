import React from 'react';

type AlertVariant = 'success' | 'warning' | 'danger' | 'info';

interface AlertProps {
  variant: AlertVariant;
  children: React.ReactNode;
  className?: string;
  dismissible?: boolean;
  onDismiss?: () => void;
}

const variantStyles: Record<AlertVariant, string> = {
  success: 'bg-success-bg border-success-light text-success',
  warning: 'bg-warning-bg border-warning-light text-warning',
  danger: 'bg-danger-bg border-danger-light text-danger',
  info: 'bg-info-bg border-info-light text-info',
};

export default function Alert({
  variant,
  children,
  className = '',
  dismissible = false,
  onDismiss,
}: AlertProps) {
  return (
    <div
      className={`p-4 rounded-xl border text-sm ${variantStyles[variant]} ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">{children}</div>
        {dismissible && onDismiss && (
          <button
            onClick={onDismiss}
            className="text-current opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Dismiss"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
