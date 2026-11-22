import { useLayoutEffect, useId, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  returnFocusTo?: HTMLElement | null;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function Modal({ isOpen, onClose, title, children, returnFocusTo, size = 'md' }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (!isOpen || !dialog) return;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      returnFocusTo?.focus({ preventScroll: true });
    };
  }, [isOpen, returnFocusTo]);

  if (!isOpen) return null;

  const sizes: Record<string, string> = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };

  const heading = <h2 id={titleId} className="text-base font-bold text-[var(--text-main)]">{title}</h2>;
  const closeButton = (
    <button type="button" onClick={onClose}
      className="workspace-modal-close p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors"
      aria-label="Закрыть">
      <X className="h-4 w-4" />
    </button>
  );

  return (
    <dialog ref={dialogRef} className="workspace-confirm-dialog" aria-labelledby={titleId}
      data-record-dialog={returnFocusTo ? true : undefined}
      onCancel={event => { event.preventDefault(); onClose(); }}
      onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className={`relative w-full ${sizes[size]} bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl shadow-xl max-h-full overflow-y-auto`}>
        {returnFocusTo ? <>
          {closeButton}
          <div className="workspace-modal-content" tabIndex={0}>
            {heading}
            {children}
          </div>
        </> : <>
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--card-border)]">
            {heading}
            {closeButton}
          </div>
          <div className="px-6 py-5">{children}</div>
        </>}
      </div>
    </dialog>
  );
}
