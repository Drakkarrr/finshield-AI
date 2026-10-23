import React from 'react';

/** Data table. `caption` is required (visually hidden unless `showCaption`) so every table is named. */
export function Table({ caption, showCaption = false, className = '', children }: {
  caption: string; showCaption?: boolean; className?: string; children: React.ReactNode;
}) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-sm">
        <caption className={showCaption ? 'text-left text-sm font-semibold text-ink px-5 py-3' : 'sr-only'}>{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: React.ReactNode }) {
  return (
    <thead className="text-left text-xs text-ink-muted border-b border-border-light">
      <tr>{children}</tr>
    </thead>
  );
}

export function TBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function Tr({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <tr className={`border-b border-border-light last:border-0 hover:bg-surface-hover transition-colors ${className}`}>{children}</tr>;
}

export function Th({ children, className = '', align = 'left', scope = 'col' }: {
  children?: React.ReactNode; className?: string; align?: 'left' | 'right'; scope?: 'col' | 'row';
}) {
  const cls = scope === 'col'
    ? 'px-5 py-3 font-medium border-b border-border-light'
    : 'px-5 py-3.5 font-medium text-ink';
  return <th scope={scope} className={`${cls} ${align === 'right' ? 'text-right' : 'text-left'} ${className}`}>{children}</th>;
}

export function Td({ children, className = '', align = 'left' }: {
  children?: React.ReactNode; className?: string; align?: 'left' | 'right';
}) {
  return <td className={`px-5 py-3.5 ${align === 'right' ? 'text-right' : ''} ${className}`}>{children}</td>;
}
