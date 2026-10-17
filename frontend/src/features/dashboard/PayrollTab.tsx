import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatDate } from '@/utils/format';
import type { PayrollData } from '@/types';

export function PayrollTab() {
  const [data, setData] = useState<PayrollData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getPayroll()
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

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Период
          </p>
          <p className="text-lg font-bold text-[var(--text-main)] mt-1">
            {data.period}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Начислено
          </p>
          <p className="text-lg font-bold font-mono text-[var(--text-main)] mt-1">
            {formatCurrency(data.total_accrued)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Выплачено
          </p>
          <p className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
            {formatCurrency(data.total_paid)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
            Задолженность
          </p>
          <p className={`text-lg font-bold font-mono mt-1 ${data.total_debt > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-[var(--text-main)]'}`}>
            {formatCurrency(data.total_debt)}
          </p>
          {data.next_payment_deadline && (
            <p className="text-xs text-[var(--text-sub)] mt-1">
              Срок: {formatDate(data.next_payment_deadline)}
            </p>
          )}
        </Card>
      </div>

      {/* Departments table */}
      <Card padding="none">
        <div className="px-5 py-3.5 border-b border-[var(--card-border)]">
          <h3 className="text-sm font-bold text-[var(--text-main)]">
            По подразделениям
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)]">
                <th className="text-left px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                  Подразделение
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                  Начислено
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                  Выплачено
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                  Долг
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-[var(--text-sub)] uppercase tracking-wider">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--card-border)]">
              {data.by_department.map((dept, i) => (
                <tr
                  key={i}
                  className="hover:bg-[var(--card-subtle)] transition-colors"
                >
                  <td className="px-4 py-3.5 font-semibold text-[var(--text-main)]">
                    {dept.department}
                  </td>
                  <td className="px-4 py-3.5 text-right font-mono text-[var(--text-sub)]">
                    {formatCurrency(dept.accrued)}
                  </td>
                  <td className="px-4 py-3.5 text-right font-mono text-[var(--text-sub)]">
                    {formatCurrency(dept.paid)}
                  </td>
                  <td className="px-4 py-3.5 text-right font-mono">
                    {dept.debt > 0 ? (
                      <span className="text-rose-600 dark:text-rose-400 font-bold">{formatCurrency(dept.debt)}</span>
                    ) : (
                      <span className="text-emerald-600 dark:text-emerald-400 font-semibold">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    {dept.debt > 0 ? (
                      <Badge variant="danger">Долг</Badge>
                    ) : (
                      <Badge variant="success">Оплачено</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

    </div>
  );
}
