import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

const base =
  'inline-flex items-center justify-center gap-2 rounded-xl transition-colors ' +
  'disabled:opacity-50 disabled:cursor-not-allowed ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2';

const variants: Record<ButtonVariant, string> = {
  // navy on accent: white on #C8870E is 3:1 and fails WCAG AA
  primary: 'bg-accent hover:bg-accent-light text-navy font-semibold',
  secondary: 'bg-surface hover:bg-bg-alt border border-border text-ink-secondary font-medium',
  danger: 'bg-danger-bg hover:bg-danger-light text-danger-fg font-medium border border-danger-light',
  ghost: 'text-ink-secondary hover:text-ink hover:bg-bg-alt font-medium',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-6 py-3 text-base',
};

/** Classes for a link that looks like a button (`<Link className={buttonClasses()}>`). */
export function buttonClasses(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', className = '') {
  return `${base} ${variants[variant]} ${sizes[size]} ${className}`;
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  type = 'button',
  children,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClasses(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && (
        <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
