import type { ButtonHTMLAttributes, ReactNode, ComponentType } from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: ComponentType<{ className?: string }>;
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon: Icon,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const base =
    'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed select-none cursor-pointer';

  const variants: Record<ButtonVariant, string> = {
    primary:
      'bg-slate-900 text-white hover:bg-slate-800 active:bg-slate-950 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white dark:active:bg-slate-200 focus:ring-slate-400 dark:focus:ring-slate-500 dark:focus:ring-offset-slate-900 shadow-2xs',
    secondary:
      'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 border border-slate-200/80 dark:border-slate-700/80 focus:ring-slate-300 dark:focus:ring-offset-slate-900 shadow-2xs',
    outline:
      'border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/80 focus:ring-slate-300 dark:focus:ring-offset-slate-900',
    ghost:
      'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 focus:ring-slate-300 dark:focus:ring-offset-slate-900',
    danger:
      'bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 focus:ring-rose-500 dark:focus:ring-offset-slate-900 shadow-2xs',
  };

  const sizes: Record<ButtonSize, string> = {
    sm: 'px-2.5 py-1.5 text-xs gap-1.5 min-h-[36px]',
    md: 'px-3.5 py-2 text-sm gap-2 min-h-[40px]',
    lg: 'px-5 py-2.5 text-base gap-2.5 min-h-[44px]',
  };

  const iconSizes: Record<ButtonSize, string> = {
    sm: 'h-3.5 w-3.5',
    md: 'h-4 w-4',
    lg: 'h-4.5 w-4.5',
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className={`${iconSizes[size]} animate-spin`} />
      ) : Icon ? (
        <Icon className={iconSizes[size]} />
      ) : null}
      {children}
    </button>
  );
}
