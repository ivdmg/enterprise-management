import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatPercent, formatDate } from '@/utils/format';
import type { Project } from '@/types';

function getRiskBadge(level: string) {
  switch (level) {
    case 'critical':
      return <Badge variant="danger">Критический</Badge>;
    case 'warning':
      return <Badge variant="warning">Внимание</Badge>;
    default:
      return <Badge variant="success">Норма</Badge>;
  }
}

export function ProjectsTab() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getProjects()
      .then(setProjects)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card padding="none">
        {/* Desktop Table View (>= 768px) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm" id="projects-table">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Объект
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Сумма договора
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-40">
                  Выполнение
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Срок сдачи
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Статус
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Штраф
                </th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr
                  key={project.id}
                  className="border-t border-slate-200 dark:border-slate-800 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900 dark:text-slate-100">
                      {project.project_name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {project.project_code} {project.curator_name ? `· ${project.curator_name}` : ''}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-900 dark:text-slate-100">
                    {formatCurrency(project.contract_sum)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            project.risk_level === 'critical'
                              ? 'bg-rose-500'
                              : project.risk_level === 'warning'
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                          style={{ width: `${project.completion_percent || 0}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-slate-600 dark:text-slate-400 w-12 text-right">
                        {formatPercent(project.completion_percent || 0)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">
                    {project.deadline_date ? formatDate(project.deadline_date) : '—'}
                    {project.days_overdue > 0 && (
                      <p className="text-xs text-rose-600 dark:text-rose-400 mt-0.5">
                        +{project.days_overdue} дн.
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {getRiskBadge(project.risk_level)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {project.penalty_amount_calculated && project.penalty_amount_calculated > 0 ? (
                      <span className="text-rose-600 dark:text-rose-400">
                        {formatCurrency(project.penalty_amount_calculated)}
                      </span>
                    ) : (
                      <span className="text-slate-400 dark:text-slate-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View (< 768px) */}
        <div className="md:hidden divide-y divide-slate-200 dark:divide-slate-800" id="projects-mobile-cards">
          {projects.map((project) => (
            <div key={project.id} className="p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                    {project.project_name}
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {project.project_code} {project.curator_name ? `· ${project.curator_name}` : ''}
                  </p>
                </div>
                <div>{getRiskBadge(project.risk_level)}</div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
                  <span className="text-[10px] uppercase font-medium text-slate-400">Сумма договора</span>
                  <p className="text-sm font-semibold font-mono text-slate-900 dark:text-slate-100 mt-0.5">
                    {formatCurrency(project.contract_sum)}
                  </p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
                  <span className="text-[10px] uppercase font-medium text-slate-400">Срок сдачи</span>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mt-0.5">
                    {project.deadline_date ? formatDate(project.deadline_date) : '—'}
                  </p>
                  {project.days_overdue > 0 && (
                    <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 block mt-0.5">
                      +{project.days_overdue} дн. просрочка
                    </span>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
                  <span>Выполнение</span>
                  <span className="font-mono font-medium">{formatPercent(project.completion_percent || 0)}</span>
                </div>
                <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      project.risk_level === 'critical'
                        ? 'bg-rose-500'
                        : project.risk_level === 'warning'
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                    }`}
                    style={{ width: `${project.completion_percent || 0}%` }}
                  />
                </div>
              </div>

              {/* Penalty */}
              {project.penalty_amount_calculated && project.penalty_amount_calculated > 0 ? (
                <div className="flex items-center justify-between text-xs bg-rose-50 dark:bg-rose-950/30 p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300">
                  <span>Расчетный штраф (44-ФЗ):</span>
                  <span className="font-mono font-bold">{formatCurrency(project.penalty_amount_calculated)}</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
