import type { ReactNode, HTMLAttributes } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export function Card({ children, padding = 'md', className = '', ...props }: CardProps) {
  const paddings: Record<string, string> = {
    none: '',
    sm: 'p-3.5',
    md: 'p-4 sm:p-5',
    lg: 'p-6',
  };

  return (
    <div
      className={`bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] transition-colors duration-150 ${paddings[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
