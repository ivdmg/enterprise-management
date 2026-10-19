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
      'bg-red-50 text-red-800 border-red-300 hover:bg-red-100 dark:bg-red-950/70 dark:text-red-200 dark:border-red-800/80',
    dot: 'bg-red-600 dark:bg-red-500',
  },
  warning: {
    container:
      'bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100 dark:bg-amber-950/70 dark:text-amber-200 dark:border-amber-800/80',
    dot: 'bg-amber-600 dark:bg-amber-500',
  },
  success: {
    container:
      'bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100 dark:bg-emerald-950/70 dark:text-emerald-200 dark:border-emerald-800/80',
    dot: 'bg-emerald-600 dark:bg-emerald-500',
  },
  info: {
    container:
      'bg-slate-100 text-slate-800 border-slate-300 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
    dot: 'bg-slate-600 dark:bg-slate-400',
  },
  neutral: {
    container:
      'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    dot: 'bg-slate-500 dark:bg-slate-400',
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
