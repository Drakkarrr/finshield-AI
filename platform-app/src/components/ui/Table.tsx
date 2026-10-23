import React from 'react';

interface TableProps {
  children: React.ReactNode;
  className?: string;
}

export default function Table({ children, className = '' }: TableProps) {
  return (
    <div className={`overflow-hidden glass ${className}`}>
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}

export function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead className="text-left text-xs text-ink-light border-b border-border-light">
      <tr>{children}</tr>
    </thead>
  );
}

export function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b border-border-light hover:bg-bg-alt transition-colors">
      {children}
    </tr>
  );
}

export function TableCell({
  children,
  className = '',
  header = false,
}: {
  children: React.ReactNode;
  className?: string;
  header?: boolean;
}) {
  const Tag = header ? 'th' : 'td';
  return (
    <Tag 
      className={`px-5 py-3.5 ${header ? 'font-medium' : ''} ${className}`}
      scope={header ? 'col' : undefined}
    >
      {children}
    </Tag>
  );
}
