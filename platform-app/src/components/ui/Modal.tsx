'use client';

import React, { useEffect, useId, useRef } from 'react';

const sizes = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-xl', '2xl': 'max-w-2xl', '3xl': 'max-w-3xl' } as const;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  size?: keyof typeof sizes;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/**
 * Native modal <dialog> (top layer; the rest of the page is inert while open), plus an explicit
 * Tab wrap, Escape to close, backdrop click to close and focus restored to the opener.
 */
export function Modal({ open, onClose, title, description, size = 'md', children, footer }: ModalProps) {
  if (!open) return null;
  return <ModalDialog onClose={onClose} title={title} description={description} size={size} footer={footer}>{children}</ModalDialog>;
}

function ModalDialog({ onClose, title, description, size = 'md', children, footer }: Omit<ModalProps, 'open'>) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descId = useId();
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const opener = document.activeElement as HTMLElement | null;
    dialog.showModal();
    (dialog.querySelector<HTMLElement>('[data-autofocus]') ?? dialog.querySelector<HTMLElement>(FOCUSABLE))?.focus();

    const onCancel = (e: Event) => { e.preventDefault(); onCloseRef.current(); }; // Escape
    const onBackdrop = (e: MouseEvent) => { if (e.target === dialog) onCloseRef.current(); };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    dialog.addEventListener('cancel', onCancel);
    dialog.addEventListener('click', onBackdrop);
    dialog.addEventListener('keydown', onKeyDown);
    return () => {
      dialog.removeEventListener('cancel', onCancel);
      dialog.removeEventListener('click', onBackdrop);
      dialog.removeEventListener('keydown', onKeyDown);
      dialog.close();
      opener?.focus?.();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      className={`w-full ${sizes[size]} max-h-modal overflow-y-auto m-auto p-0 bg-surface border border-border rounded-2xl shadow-dropdown text-ink backdrop:bg-navy/60 backdrop:backdrop-blur-sm`}
    >
      <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-4 border-b border-border-light">
        <div>
          <h2 id={titleId} className="text-lg font-bold text-ink">{title}</h2>
          {description && <p id={descId} className="text-sm text-ink-muted mt-0.5">{description}</p>}
        </div>
        <button
          type="button"
          onClick={() => onCloseRef.current()}
          className="p-1 rounded-lg text-ink-muted hover:text-ink hover:bg-bg-alt"
          aria-label="Close dialog"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="px-6 py-5">{children}</div>
      {footer && <div className="flex flex-wrap items-center justify-end gap-3 px-6 pb-6">{footer}</div>}
    </dialog>
  );
}
