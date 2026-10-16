import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatPercent, formatDate } from '@/utils/format';
import type { Project, TenderStage } from '@/types';
import {
  ShieldAlert,
  ShieldCheck,
  Search,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Layers,
} from 'lucide-react';

interface StageDefinition {
  id: TenderStage;
  label: string;
  stepNumber: number;
}

const STAGES: StageDefinition[] = [
  { id: 'preparation', label: 'Подготовка', stepNumber: 1 },
  { id: 'submitted', label: 'Подано', stepNumber: 2 },
  { id: 'bidding', label: 'Торги', stepNumber: 3 },
  { id: 'won', label: 'Победа', stepNumber: 4 },
  { id: 'contract', label: 'Контракт', stepNumber: 5 },
];

function getStageIndex(stage?: TenderStage): number {
  if (!stage) return 0;
  const idx = STAGES.findIndex((s) => s.id === stage);
  return idx >= 0 ? idx : 0;
}

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
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadProjects = () => {
    setLoading(true);
    apiClient
      .getProjects()
      .then(setProjects)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleStageChange = async (projectId: string, newStage: TenderStage) => {
    // Optimistic update
    setUpdatingId(projectId);
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, tender_stage: newStage } : p))
    );

    try {
      await apiClient.updateProjectTenderStage(projectId, newStage);
    } catch (err) {
      console.error('Failed to update stage:', err);
      // Revert if error
      loadProjects();
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredProjects = projects.filter((p) => {
    if (stageFilter !== 'all' && p.tender_stage !== stageFilter) return false;
    if (riskFilter !== 'all' && p.risk_level !== riskFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = p.project_name.toLowerCase().includes(q);
      const matchCode = p.project_code?.toLowerCase().includes(q);
      const matchCustomer = p.customer_name?.toLowerCase().includes(q);
      const matchCurator = p.curator_name?.toLowerCase().includes(q);
      if (!matchName && !matchCode && !matchCustomer && !matchCurator) return false;
    }
    return true;
  });

  const totalContractSum = filteredProjects.reduce((acc, p) => acc + p.contract_sum, 0);
  const criticalBgCount = projects.filter(
    (p) => p.bank_guarantee && p.bank_guarantee.days_remaining < 5
  ).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Header & Summary Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Building2 className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Тендеры и объекты строительства
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Линейный контроль стадий 44-ФЗ / 223-ФЗ, банковские гарантии и исполнение контрактов
          </p>
        </div>

        {/* Quick summary metrics */}
        <div className="flex flex-wrap items-center gap-2">
          {criticalBgCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-400 text-xs font-semibold">
              <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
              <span>
                Риск РНП по БГ: {criticalBgCount}{' '}
                {criticalBgCount === 1 ? 'объект' : 'объекта'}
              </span>
            </div>
          )}
          <div className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium">
            Портфель: <span className="font-mono font-semibold">{formatCurrency(totalContractSum)}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card padding="sm">
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по названию, шифру, заказчику или куратору..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400"
              />
            </div>

            {/* Risk filter */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
              <span className="text-[11px] uppercase font-semibold text-slate-400 whitespace-nowrap mr-1">
                Риск:
              </span>
              {[
                { id: 'all', label: 'Все' },
                { id: 'critical', label: 'Критич.' },
                { id: 'warning', label: 'Внимание' },
                { id: 'normal', label: 'Норма' },
              ].map((rf) => (
                <button
                  key={rf.id}
                  onClick={() => setRiskFilter(rf.id)}
                  className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap ${
                    riskFilter === rf.id
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {rf.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tender Stage Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-slate-100 dark:border-slate-800/80">
            <span className="text-[11px] uppercase font-semibold text-slate-400 whitespace-nowrap mr-1 flex items-center gap-1">
              <Layers className="h-3 w-3" />
              Стадия:
            </span>
            <button
              onClick={() => setStageFilter('all')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap ${
                stageFilter === 'all'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              Все стадии ({projects.length})
            </button>
            {STAGES.map((s) => {
              const count = projects.filter((p) => p.tender_stage === s.id).length;
              return (
                <button
                  key={s.id}
                  onClick={() => setStageFilter(s.id)}
                  className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap ${
                    stageFilter === s.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {s.label} ({count})
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Main Content Area */}
      <Card padding="none">
        {/* Desktop Table View (>= 768px) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm" id="projects-table">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-64">
                  Объект и заказчик
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Линейный степпер закупки
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-44">
                  Банковская гарантия
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Сумма договора
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-36">
                  Выполнение
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Срок сдачи
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Риск
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400 text-sm">
                    Объектов по выбранным фильтрам не найдено
                  </td>
                </tr>
              ) : (
                filteredProjects.map((project) => {
                  const currentStageIdx = getStageIndex(project.tender_stage);
                  const bg = project.bank_guarantee;
                  const isBgCritical = bg && (bg.days_remaining < 5 || bg.is_critical);

                  return (
                    <tr
                      key={project.id}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Project info */}
                      <td className="px-4 py-3.5 align-top">
                        <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                          {project.project_name}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          {project.project_code} {project.customer_name ? `· ${project.customer_name}` : ''}
                        </p>
                        {project.curator_name && (
                          <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                            Куратор: {project.curator_name}
                          </p>
                        )}
                      </td>

                      {/* Linear Stepper */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-1">
                            {STAGES.map((stage, idx) => {
                              const isCompleted = idx < currentStageIdx;
                              const isCurrent = idx === currentStageIdx;

                              return (
                                <div key={stage.id} className="flex items-center">
                                  <button
                                    type="button"
                                    onClick={() => handleStageChange(project.id, stage.id)}
                                    title={`Сменить стадию на: ${stage.label}`}
                                    disabled={updatingId === project.id}
                                    className={`px-2 py-1 rounded text-[11px] font-medium transition-all flex items-center gap-1 cursor-pointer select-none ${
                                      isCurrent
                                        ? 'bg-indigo-600 text-white font-semibold ring-1 ring-indigo-500 shadow-sm'
                                        : isCompleted
                                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/40'
                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}
                                  >
                                    {isCompleted ? (
                                      <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                                    ) : (
                                      <span className="w-3 text-center">{stage.stepNumber}</span>
                                    )}
                                    <span>{stage.label}</span>
                                  </button>

                                  {idx < STAGES.length - 1 && (
                                    <div
                                      className={`w-3.5 h-[2px] mx-0.5 ${
                                        idx < currentStageIdx
                                          ? 'bg-emerald-500 dark:bg-emerald-600'
                                          : 'bg-slate-200 dark:bg-slate-700'
                                      }`}
                                    />
                                  )}
                                </div>
                              );
                            })}
                          </div>
                          <p className="text-[11px] text-slate-400">
                            Текущий этап:{' '}
                            <span className="font-semibold text-slate-700 dark:text-slate-300">
                              {STAGES[currentStageIdx]?.label}
                            </span>{' '}
                            (кликните для изменения)
                          </p>
                        </div>
                      </td>

                      {/* Bank Guarantee */}
                      <td className="px-4 py-3.5 align-top">
                        {bg ? (
                          <div
                            className={`p-2 rounded-lg border text-xs space-y-1 ${
                              isBgCritical
                                ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/50 text-rose-800 dark:text-rose-300'
                                : 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300'
                            }`}
                          >
                            <div className="flex items-center gap-1.5 font-semibold">
                              {isBgCritical ? (
                                <>
                                  <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
                                  <span>Риск РНП! &le; {bg.days_remaining} дн.</span>
                                </>
                              ) : (
                                <>
                                  <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                  <span>БГ активна ({bg.days_remaining} дн.)</span>
                                </>
                              )}
                            </div>
                            <p className="text-[11px] opacity-90">
                              {bg.bank_name} · {formatCurrency(bg.amount)}
                            </p>
                            <p className="text-[10px] opacity-75">
                              До {formatDate(bg.expiry_date)}
                            </p>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">Не требуется</span>
                        )}
                      </td>

                      {/* Contract Sum */}
                      <td className="px-4 py-3.5 text-right font-mono text-slate-900 dark:text-slate-100 align-top">
                        <p className="font-semibold">{formatCurrency(project.contract_sum)}</p>
                        {project.paid_sum !== undefined && (
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Оплачено: {formatCurrency(project.paid_sum)}
                          </p>
                        )}
                      </td>

                      {/* Completion Progress */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
                              {formatPercent(project.completion_percent || 0)}
                            </span>
                            <span className="text-[11px] text-slate-400">
                              {formatCurrency(project.completed_sum)}
                            </span>
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
                      </td>

                      {/* Deadline & Penalty */}
                      <td className="px-4 py-3.5 text-right text-slate-700 dark:text-slate-300 align-top">
                        <p className="font-medium">
                          {project.deadline_date ? formatDate(project.deadline_date) : '—'}
                        </p>
                        {project.days_overdue > 0 ? (
                          <p className="text-xs text-rose-600 dark:text-rose-400 font-semibold mt-0.5">
                            +{project.days_overdue} дн. просрочка
                          </p>
                        ) : (
                          <p className="text-[11px] text-slate-400 mt-0.5">В графике</p>
                        )}
                        {project.penalty_amount_calculated && project.penalty_amount_calculated > 0 ? (
                          <p className="text-xs text-rose-600 dark:text-rose-400 font-mono font-semibold mt-1">
                            Штраф: {formatCurrency(project.penalty_amount_calculated)}
                          </p>
                        ) : null}
                      </td>

                      {/* Risk */}
                      <td className="px-4 py-3.5 text-center align-top">
                        {getRiskBadge(project.risk_level)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View (< 768px) */}
        <div className="md:hidden divide-y divide-slate-200 dark:divide-slate-800" id="projects-mobile-cards">
          {filteredProjects.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              Объектов по выбранным фильтрам не найдено
            </div>
          ) : (
            filteredProjects.map((project) => {
              const currentStageIdx = getStageIndex(project.tender_stage);
              const bg = project.bank_guarantee;
              const isBgCritical = bg && (bg.days_remaining < 5 || bg.is_critical);

              return (
                <div key={project.id} className="p-4 space-y-3.5">
                  {/* Title & Risk */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                        {project.project_name}
                      </h4>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {project.project_code} {project.customer_name ? `· ${project.customer_name}` : ''}
                      </p>
                      {project.curator_name && (
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Куратор: {project.curator_name}
                        </p>
                      )}
                    </div>
                    <div>{getRiskBadge(project.risk_level)}</div>
                  </div>

                  {/* Mobile Linear Stepper */}
                  <div className="bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-lg border border-slate-200/80 dark:border-slate-800 space-y-2">
                    <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                      Стадия закупки (нажмите для смены):
                    </span>
                    <div className="grid grid-cols-5 gap-1">
                      {STAGES.map((stage, idx) => {
                        const isCompleted = idx < currentStageIdx;
                        const isCurrent = idx === currentStageIdx;

                        return (
                          <button
                            key={stage.id}
                            type="button"
                            onClick={() => handleStageChange(project.id, stage.id)}
                            disabled={updatingId === project.id}
                            className={`py-1.5 px-0.5 rounded text-[10px] text-center font-medium transition-all min-h-[36px] flex flex-col items-center justify-center ${
                              isCurrent
                                ? 'bg-indigo-600 text-white font-bold ring-1 ring-indigo-500'
                                : isCompleted
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                                : 'bg-slate-200/60 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400'
                            }`}
                          >
                            <span>{stage.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Bank Guarantee Alert (Mobile) */}
                  {bg && (
                    <div
                      className={`p-2.5 rounded-lg border text-xs space-y-1 ${
                        isBgCritical
                          ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/50 text-rose-800 dark:text-rose-300'
                          : 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-semibold">
                          {isBgCritical ? (
                            <>
                              <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
                              <span>Риск РНП! Осталось {bg.days_remaining} дн.</span>
                            </>
                          ) : (
                            <>
                              <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                              <span>Банковская гарантия активна</span>
                            </>
                          )}
                        </div>
                        <span className="font-mono font-semibold">{formatCurrency(bg.amount)}</span>
                      </div>
                      <p className="text-[11px] opacity-80">
                        {bg.bank_name} · Срок до {formatDate(bg.expiry_date)}
                      </p>
                    </div>
                  )}

                  {/* Financial & Deadline Grid */}
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
                      <span>Выполнение работ</span>
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

                  {/* Penalty Alert */}
                  {project.penalty_amount_calculated && project.penalty_amount_calculated > 0 ? (
                    <div className="flex items-center justify-between text-xs bg-rose-50 dark:bg-rose-950/30 p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300">
                      <span className="flex items-center gap-1.5">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        Расчетный штраф (44-ФЗ):
                      </span>
                      <span className="font-mono font-bold">{formatCurrency(project.penalty_amount_calculated)}</span>
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </Card>
    </div>
  );
}
