import { useEffect, useRef, type ReactNode } from 'react';
import { Button } from './Button';
import { ShieldCheck, AlertTriangle, AlertOctagon, ArrowRight, X } from 'lucide-react';

export interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  description: string | ReactNode;
  currentStatusLabel?: string;
  newStatusLabel?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'danger' | 'warning';
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ConfirmModal({
  isOpen,
  title,
  description,
  currentStatusLabel,
  newStatusLabel,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  variant = 'default',
  onConfirm,
  onCancel,
  isLoading = false,
}: ConfirmModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Lock scroll
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Escape listener
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) {
        onCancel();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleEsc);
    }
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onCancel, isLoading]);

  if (!isOpen) return null;

  const iconConfig = {
    default: {
      Icon: ShieldCheck,
      containerClass: 'bg-[var(--card-subtle)] text-[var(--text-main)] border border-[var(--card-border)]',
    },
    warning: {
      Icon: AlertTriangle,
      containerClass: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60',
    },
    danger: {
      Icon: AlertOctagon,
      containerClass: 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/60',
    },
  }[variant];

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current && !isLoading) {
          onCancel();
        }
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-150" />

      {/* Modal Dialog */}
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        className="relative w-full max-w-md bg-[var(--card-bg)] border border-[var(--card-border)] text-[var(--text-main)] shadow-2xl rounded-2xl p-5 sm:p-6 z-10 animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className="absolute top-4 right-4 p-1.5 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors disabled:opacity-50 cursor-pointer"
          aria-label="Закрыть"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Header with Icon */}
        <div className="flex items-start gap-3.5">
          <div className={`p-2.5 rounded-xl shrink-0 ${iconConfig.containerClass}`}>
            <iconConfig.Icon className="h-5 w-5" />
          </div>
          <div className="space-y-1 pr-6">
            <h3
              id="confirm-modal-title"
              className="text-base font-semibold text-[var(--text-main)] leading-snug"
            >
              {title}
            </h3>
            <div className="text-xs sm:text-sm text-[var(--text-sub)] leading-relaxed">
              {description}
            </div>
          </div>
        </div>

        {/* Status Transition Visual Widget (Foolproof verification) */}
        {currentStatusLabel && newStatusLabel && (
          <div className="mt-4 p-3 rounded-xl bg-[var(--card-subtle)] border border-[var(--card-border)] flex items-center justify-between text-xs">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-[var(--text-muted)] mb-0.5">
                Текущий статус
              </span>
              <span className="font-medium text-[var(--text-sub)]">
                {currentStatusLabel}
              </span>
            </div>

            <div className="p-1.5 rounded-full bg-[var(--card-bg)] text-[var(--text-muted)] border border-[var(--card-border)] mx-2">
              <ArrowRight className="h-3.5 w-3.5" />
            </div>

            <div className="flex flex-col text-right">
              <span className="text-[10px] uppercase font-semibold text-[var(--text-muted)] mb-0.5">
                Новый статус
              </span>
              <span className="font-semibold text-[var(--text-main)]">
                {newStatusLabel}
              </span>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-6 flex items-center justify-end gap-2.5">
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 sm:flex-initial"
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            isLoading={isLoading}
            className="flex-1 sm:flex-initial"
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
}
