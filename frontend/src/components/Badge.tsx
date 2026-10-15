import type { ReactNode } from 'react';

type BadgeVariant = 'danger' | 'warning' | 'success' | 'info' | 'neutral';

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  danger: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  warning: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  success: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  info: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  neutral: 'bg-slate-500/10 text-slate-600 dark:text-slate-400',
};

export function Badge({ variant = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
