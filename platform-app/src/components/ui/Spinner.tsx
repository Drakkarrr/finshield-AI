import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeStyles = {
  sm: 'w-4 h-4 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-10 h-10 border-2',
};

export default function Spinner({ size = 'md', className = '' }: SpinnerProps) {
  return (
    <div
      className={`${sizeStyles[size]} border-accent/30 border-t-accent rounded-full animate-spin ${className}`}
    />
  );
}
