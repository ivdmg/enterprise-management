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
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
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
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Приходы
          </p>
          <p className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {formatCurrencyShort(data.total_incoming)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Расходы
          </p>
          <p className="text-xl font-bold font-mono text-red-600 dark:text-red-400 mt-1">
            {formatCurrencyShort(data.total_outgoing)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Чистый поток
          </p>
          <p className={`text-xl font-bold font-mono mt-1 ${data.net_cash_flow >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {formatCurrencyShort(data.net_cash_flow)}
          </p>
        </Card>
      </div>

      {/* Chart */}
      <Card>
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <h3 className="text-sm font-bold text-[var(--text-main)]">
            Динамика движения денежных средств
          </h3>
          <span className="text-[11px] text-[var(--text-muted)] hidden sm:inline">
            Приходы и расходы по дням
          </span>
        </div>
        <div className="h-60 sm:h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" opacity={0.5} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: 'var(--text-sub)' }}
                axisLine={{ stroke: 'var(--card-border)' }}
                tickLine={false}
                minTickGap={20}
              />
              <YAxis
                tickFormatter={(v) => formatCurrencyShort(v)}
                tick={{ fontSize: 10, fill: 'var(--text-sub)' }}
                axisLine={false}
                tickLine={false}
                width={55}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--card-bg)',
                  borderColor: 'var(--card-border)',
                  borderRadius: '0.75rem',
                  fontSize: '0.75rem',
                  color: 'var(--text-main)',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                  padding: '8px 12px',
                }}
                formatter={(value: any, name: any) => [
                  formatCurrency(Number(value) || 0),
                  name === 'incoming' ? 'Приходы' : 'Расходы',
                ]}
                labelFormatter={(label) => `Дата: ${label}`}
              />
              <Legend
                formatter={(value) => (value === 'incoming' ? 'Приходы' : 'Расходы')}
                wrapperStyle={{ fontSize: '0.75rem', paddingTop: '8px' }}
              />
              <Area
                type="monotone"
                dataKey="incoming"
                stroke="#16A34A"
                fill="#16A34A"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="outgoing"
                stroke="#DC2626"
                fill="#DC2626"
                fillOpacity={0.15}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Debtors & Creditors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-bold text-[var(--text-main)] mb-3">
            Дебиторы (нам должны)
          </h3>
          <div className="space-y-0">
            {data.top_debtors.map((d, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-[var(--card-border)] last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--text-main)]">{d.counterparty}</p>
                  {d.overdue_days !== undefined && d.overdue_days > 0 && (
                    <Badge variant="danger" className="mt-0.5">Просрочка {d.overdue_days} дн.</Badge>
                  )}
                </div>
                <p className="text-sm font-mono font-bold text-right text-[var(--text-main)]">
                  {formatCurrency(d.debt_sum)}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-[var(--text-main)] mb-3">
            Кредиторы (мы должны)
          </h3>
          <div className="space-y-0">
            {data.top_creditors.map((c, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-[var(--card-border)] last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--text-main)]">{c.counterparty}</p>
                  {c.payment_due_date && (
                    <p className="text-xs text-[var(--text-sub)] mt-0.5">
                      Срок оплаты: {formatShortDate(c.payment_due_date)}
                    </p>
                  )}
                </div>
                <p className="text-sm font-mono font-bold text-right text-[var(--text-main)]">
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
