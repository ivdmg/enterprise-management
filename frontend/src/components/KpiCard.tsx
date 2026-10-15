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
    <Card>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            {title}
          </p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
          )}
          {trend && (
            <p
              className={`text-xs font-medium ${
                trend.positive
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-rose-600 dark:text-rose-400'
              }`}
            >
              {trend.value}
            </p>
          )}
        </div>
        <div className="p-2 rounded-md bg-slate-100 dark:bg-slate-800">
          <Icon className="h-5 w-5 text-slate-500 dark:text-slate-400" />
        </div>
      </div>
    </Card>
  );
}
