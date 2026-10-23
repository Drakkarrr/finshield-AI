import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-success-bg text-success border-success-light',
  warning: 'bg-warning-bg text-warning border-warning-light',
  danger: 'bg-danger-bg text-danger border-danger-light',
  info: 'bg-info-bg text-info border-info-light',
  neutral: 'bg-bg-alt text-ink-secondary border-border',
};

export default function Badge({ variant, children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
