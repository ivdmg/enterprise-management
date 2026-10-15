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
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Период
          </p>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100 mt-1">
            {data.period}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Начислено
          </p>
          <p className="text-lg font-semibold text-slate-900 dark:text-slate-100 mt-1">
            {formatCurrency(data.total_accrued)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Выплачено
          </p>
          <p className="text-lg font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
            {formatCurrency(data.total_paid)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Задолженность
          </p>
          <p className={`text-lg font-semibold mt-1 ${data.total_debt > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-slate-100'}`}>
            {formatCurrency(data.total_debt)}
          </p>
          {data.next_payment_deadline && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Срок: {formatDate(data.next_payment_deadline)}
            </p>
          )}
        </Card>
      </div>

      {/* Departments table */}
      <Card padding="none">
        <div className="px-4 sm:px-5 py-3 border-b border-slate-200 dark:border-slate-800">
          <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
            По подразделениям
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Подразделение
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Начислено
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Выплачено
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Долг
                </th>
                <th className="text-center px-4 py-2.5 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody>
              {data.by_department.map((dept, i) => (
                <tr
                  key={i}
                  className="border-t border-slate-200 dark:border-slate-800 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                    {dept.department}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                    {formatCurrency(dept.accrued)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-700 dark:text-slate-300">
                    {formatCurrency(dept.paid)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {dept.debt > 0 ? (
                      <span className="text-rose-600 dark:text-rose-400">{formatCurrency(dept.debt)}</span>
                    ) : (
                      <span className="text-emerald-600 dark:text-emerald-400">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
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
