import type { ReactNode } from 'react';

export type BadgeVariant = 'danger' | 'warning' | 'success' | 'info' | 'neutral';

export interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, { container: string; dot: string }> = {
  danger: {
    container:
      'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-900/50',
    dot: 'bg-rose-500',
  },
  warning: {
    container:
      'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-900/50',
    dot: 'bg-amber-500',
  },
  success: {
    container:
      'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/50',
    dot: 'bg-emerald-500',
  },
  info: {
    container:
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    dot: 'bg-slate-500',
  },
  neutral: {
    container:
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    dot: 'bg-slate-400',
  },
};

export function Badge({ variant = 'neutral', children, className = '', dot = false }: BadgeProps) {
  const styles = variantStyles[variant];

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border transition-colors ${styles.container} ${className}`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} />}
      {children}
    </span>
  );
}
