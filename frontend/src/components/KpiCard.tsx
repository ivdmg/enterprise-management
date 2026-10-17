import type { LucideIcon } from 'lucide-react';
import { Card } from './Card';

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: LucideIcon;
  trend?: {
    value: string;
    positive?: boolean;
  };
}

export function KpiCard({ title, value, subtitle, icon: Icon, trend }: KpiCardProps) {
  return (
    <Card padding="md">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-[var(--text-sub)] tracking-tight">
          {title}
        </span>
        <Icon className="h-4 w-4 text-slate-400 dark:text-slate-500 shrink-0 mt-0.5" />
      </div>

      <div className="mt-2.5">
        <div className="text-2xl sm:text-3xl font-bold font-mono tracking-tight text-[var(--text-main)]">
          {value}
        </div>
        {subtitle && (
          <p className="text-xs text-[var(--text-sub)] mt-1 font-medium">{subtitle}</p>
        )}
        {trend && (
          <p
            className={`text-xs font-semibold mt-1 flex items-center gap-1 ${
              trend.positive
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-600 dark:text-rose-400'
            }`}
          >
            {trend.value}
          </p>
        )}
      </div>
    </Card>
  );
}
