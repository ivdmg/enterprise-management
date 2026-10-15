import { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatCurrencyShort, formatShortDate } from '@/utils/format';
import type { FinanceData } from '@/types';

export function FinanceTab() {
  const [data, setData] = useState<FinanceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getFinanceData()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  const chartData = data.dynamics.map((d) => ({
    ...d,
    label: formatShortDate(d.date),
  }));

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Приходы
          </p>
          <p className="text-xl font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
            {formatCurrencyShort(data.total_incoming)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Расходы
          </p>
          <p className="text-xl font-semibold text-rose-600 dark:text-rose-400 mt-1">
            {formatCurrencyShort(data.total_outgoing)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Чистый поток
          </p>
          <p className={`text-xl font-semibold mt-1 ${data.net_cash_flow >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
            {formatCurrencyShort(data.net_cash_flow)}
          </p>
        </Card>
      </div>

      {/* Chart */}
      <Card>
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-4">
          Динамика движения денежных средств
        </h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-surface-200)" opacity={0.5} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: 'var(--color-surface-500)' }}
                axisLine={{ stroke: 'var(--color-surface-200)' }}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v) => formatCurrencyShort(v)}
                tick={{ fontSize: 11, fill: 'var(--color-surface-500)' }}
                axisLine={false}
                tickLine={false}
                width={70}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '0.375rem',
                  fontSize: '0.75rem',
                }}
                formatter={(value: any, name: any) => [
                  formatCurrency(Number(value) || 0),
                  name === 'incoming' ? 'Приходы' : 'Расходы',
                ]}
                labelFormatter={() => ''}
              />
              <Legend
                formatter={(value) => (value === 'incoming' ? 'Приходы' : 'Расходы')}
                wrapperStyle={{ fontSize: '0.75rem' }}
              />
              <Area
                type="monotone"
                dataKey="incoming"
                stroke="#059669"
                fill="#059669"
                fillOpacity={0.1}
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="outgoing"
                stroke="#E11D48"
                fill="#E11D48"
                fillOpacity={0.1}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Debtors & Creditors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
            Дебиторы (нам должны)
          </h3>
          <div className="space-y-0">
            {data.top_debtors.map((d, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0"
              >
                <div>
                  <p className="text-sm text-slate-900 dark:text-slate-100">{d.counterparty}</p>
                  {d.overdue_days !== undefined && d.overdue_days > 0 && (
                    <Badge variant="danger" className="mt-0.5">Просрочка {d.overdue_days} дн.</Badge>
                  )}
                </div>
                <p className="text-sm font-mono font-medium text-right text-slate-900 dark:text-slate-100">
                  {formatCurrency(d.debt_sum)}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
            Кредиторы (мы должны)
          </h3>
          <div className="space-y-0">
            {data.top_creditors.map((c, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0"
              >
                <div>
                  <p className="text-sm text-slate-900 dark:text-slate-100">{c.counterparty}</p>
                  {c.payment_due_date && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Срок оплаты: {formatShortDate(c.payment_due_date)}
                    </p>
                  )}
                </div>
                <p className="text-sm font-mono font-medium text-right text-slate-900 dark:text-slate-100">
                  {formatCurrency(c.debt_sum)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
