import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Select } from '@/components/Select';
import { ConfirmModal } from '@/components/ConfirmModal';
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
  Info,
  FileSpreadsheet,
  ExternalLink,
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

// Compact Bank Guarantee formatted widget (FE-3.2)
function BankGuaranteeWidget({ bg }: { bg?: Project['bank_guarantee'] }) {
  if (!bg) {
    return (
      <span className="text-xs text-[var(--text-muted)] font-normal">
        Не требуется
      </span>
    );
  }

  const isCritical = bg.days_remaining < 5 || bg.is_critical;
  const isWarning = bg.days_remaining >= 5 && bg.days_remaining <= 14;

  return (
    <div
      className={`group relative p-2 rounded-xl border text-xs transition-all max-w-full overflow-hidden ${
        isCritical
          ? 'bg-red-50/80 border-red-300 text-red-900 dark:bg-red-950/40 dark:border-red-800/80 dark:text-red-200'
          : isWarning
          ? 'bg-amber-50/80 border-amber-300 text-amber-900 dark:bg-amber-950/40 dark:border-amber-800/80 dark:text-amber-200'
          : 'bg-[var(--card-subtle)] border-[var(--card-border)] text-[var(--text-main)]'
      }`}
    >
      {/* 1st row: Status indicator + remaining days */}
      <div className="flex items-center justify-between gap-1.5 leading-tight">
        <div className="flex items-center gap-1.5 font-semibold truncate">
          {isCritical ? (
            <ShieldAlert className="h-3.5 w-3.5 text-red-600 dark:text-red-400 shrink-0" />
          ) : (
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          )}
          <span className="truncate">
            {isCritical ? 'Риск РНП!' : 'БГ активна'}
          </span>
        </div>
        <span
          className={`font-mono text-[10px] font-semibold px-1.5 py-0.2 rounded shrink-0 ${
            isCritical
              ? 'bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200'
              : 'bg-[var(--card-bg)] text-[var(--text-sub)]'
          }`}
        >
          {bg.days_remaining} дн.
        </span>
      </div>

      {/* 2nd row: Bank name + Short currency amount */}
      <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-sub)]">
        <span className="truncate max-w-[85px]" title={bg.bank_name}>
          {bg.bank_name}
        </span>
        <span className="font-mono font-medium shrink-0 ml-1">
          {formatCurrency(bg.amount)}
        </span>
      </div>

      {/* Tooltip on hover with full metadata */}
      <div className="pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-30 w-56 p-2.5 rounded-xl bg-[var(--card-bg)] border border-[var(--card-border)] shadow-xl text-xs text-[var(--text-main)] space-y-1">
        <div className="flex items-center justify-between font-semibold">
          <span>{bg.bank_name}</span>
          <span className="font-mono">{formatCurrency(bg.amount)}</span>
        </div>
        <div className="text-[11px] text-[var(--text-sub)] space-y-0.5">
          <p>Срок действия: до {formatDate(bg.expiry_date)}</p>
          <p>Остаток срока: {bg.days_remaining} календарных дней</p>
          {isCritical && (
            <p className="text-red-600 dark:text-red-400 font-medium">
              Внимание: срок продления истекает, риск включения в РНП!
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export interface ProjectsTabProps {
  highlightProjectId?: string | null;
  onClearHighlight?: () => void;
}

export function ProjectsTab({ highlightProjectId, onClearHighlight }: ProjectsTabProps = {}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);

  // Auto-highlight effect when navigated from FirePanel / FireDetailView
  useEffect(() => {
    if (highlightProjectId) {
      setActiveHighlightId(highlightProjectId);
      setSearchQuery('');
      setStageFilter('all');
      setRiskFilter('all');

      const scrollTimer = setTimeout(() => {
        const el =
          document.getElementById(`project-row-${highlightProjectId}`) ||
          document.getElementById(`project-card-${highlightProjectId}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 200);

      const fadeTimer = setTimeout(() => {
        setActiveHighlightId(null);
        if (onClearHighlight) onClearHighlight();
      }, 4000);

      return () => {
        clearTimeout(scrollTimer);
        clearTimeout(fadeTimer);
      };
    }
  }, [highlightProjectId]);

  // ConfirmModal state for tender stepper (FE-3.3)
  const [pendingStageChange, setPendingStageChange] = useState<{
    project: Project;
    targetStage: StageDefinition;
  } | null>(null);

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

  // Triggered when user clicks stage in stepper
  const handleStageClick = (project: Project, stage: StageDefinition) => {
    // If clicking current stage, do nothing
    if (project.tender_stage === stage.id) return;

    // Open confirmation modal
    setPendingStageChange({
      project,
      targetStage: stage,
    });
  };

  // Confirmed in modal
  const handleConfirmStageChange = async () => {
    if (!pendingStageChange) return;
    const { project, targetStage } = pendingStageChange;
    const projectId = project.id;
    const newStage = targetStage.id;

    setUpdatingId(projectId);
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, tender_stage: newStage } : p))
    );
    setPendingStageChange(null);

    try {
      await apiClient.updateProjectTenderStage(projectId, newStage);
    } catch (err) {
      console.error('Failed to update stage:', err);
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
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const currentStageDef = pendingStageChange
    ? STAGES.find((s) => s.id === pendingStageChange.project.tender_stage)
    : null;

  return (
    <div className="space-y-4" id="projects-tab-section">
      {/* Top Header & Summary Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-main)] flex items-center gap-2">
            <Building2 className="h-5 w-5 text-[var(--text-main)]" />
            Тендеры и объекты строительства
          </h2>
          <p className="text-xs text-[var(--text-sub)]">
            Линейный контроль стадий 44-ФЗ / 223-ФЗ, банковские гарантии и исполнение контрактов
          </p>
        </div>

        {/* Quick summary metrics */}
        <div className="flex flex-wrap items-center gap-2">
          {criticalBgCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-900/60 text-red-900 dark:text-red-200 text-xs font-semibold">
              <ShieldAlert className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <span>
                Риск РНП по БГ: {criticalBgCount}{' '}
                {criticalBgCount === 1 ? 'объект' : 'объекта'}
              </span>
            </div>
          )}
          <div className="px-3 py-1.5 rounded-xl bg-[var(--card-subtle)] text-[var(--text-sub)] text-xs font-medium border border-[var(--card-border)]">
            Портфель: <span className="font-mono font-semibold text-[var(--text-main)]">{formatCurrency(totalContractSum)}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card padding="sm">
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по названию, шифру, заказчику или куратору..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] placeholder:text-[var(--text-muted)] min-h-[38px]"
              />
            </div>

            {/* Risk filter (desktop pills) */}
            <div className="hidden md:flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
              <span className="text-[11px] uppercase font-semibold text-[var(--text-muted)] whitespace-nowrap mr-1">
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
                  className={`px-3 py-1.5 text-xs rounded-xl font-medium transition-colors whitespace-nowrap cursor-pointer min-h-[34px] ${
                    riskFilter === rf.id
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                      : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
                  }`}
                >
                  {rf.label}
                </button>
              ))}
            </div>
          </div>

          {/* Mobile Filter Dropdowns (< md) - No Overflow */}
          <div className="md:hidden grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 border-t border-[var(--card-border)]">
            <div>
              <label className="text-[10px] uppercase font-semibold text-[var(--text-muted)] block mb-1">
                Уровень риска:
              </label>
              <Select
                options={[
                  { value: 'all', label: 'Все уровни риска' },
                  { value: 'critical', label: 'Критический риск' },
                  { value: 'warning', label: 'Внимание' },
                  { value: 'normal', label: 'Норма' },
                ]}
                value={riskFilter}
                onChange={setRiskFilter}
                size="md"
                className="w-full"
                id="mobile-risk-filter-select"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-semibold text-[var(--text-muted)] block mb-1">
                Стадия закупки:
              </label>
              <Select
                options={[
                  { value: 'all', label: `Все стадии (${projects.length})` },
                  ...STAGES.map((s) => ({
                    value: s.id,
                    label: `${s.stepNumber}. ${s.label} (${projects.filter((p) => p.tender_stage === s.id).length})`,
                  })),
                ]}
                value={stageFilter}
                onChange={setStageFilter}
                size="md"
                className="w-full"
                id="mobile-stage-filter-select"
              />
            </div>
          </div>

          {/* Tender Stage Filter Pills (desktop only >= md) */}
          <div className="hidden md:flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-[var(--card-border)]">
            <span className="text-[11px] uppercase font-semibold text-[var(--text-muted)] whitespace-nowrap mr-1 flex items-center gap-1">
              <Layers className="h-3 w-3" />
              Стадия:
            </span>
            <button
              onClick={() => setStageFilter('all')}
              className={`px-3 py-1 text-xs rounded-xl font-medium transition-colors whitespace-nowrap cursor-pointer min-h-[32px] ${
                stageFilter === 'all'
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
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
                  className={`px-3 py-1 text-xs rounded-xl font-medium transition-colors whitespace-nowrap cursor-pointer min-h-[32px] ${
                    stageFilter === s.id
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                      : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
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
        {/* ============================================================ */}
        {/* DESKTOP TABLE VIEW (>= 768px): All 5 Stage Names Visible, No Vertical Lines */}
        {/* Proportions: Объект 21%, Степпер 35%, БГ 17%, Сумма 12%, Срок 8%, Риск 7% */}
        {/* ============================================================ */}
        <div className="hidden md:block overflow-x-hidden">
          <table className="w-full text-sm table-fixed" id="projects-table">
            <thead>
              <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)] text-xs text-[var(--text-sub)] uppercase font-semibold">
                {/* 1. Объект и заказчик (21%) */}
                <th className="text-left px-3 py-3 w-[21%]">
                  Объект и заказчик
                </th>
                {/* 2. Степпер закупки (35%) - Все 5 названий */}
                <th className="text-left px-3 py-3 w-[35%]">
                  Линейный степпер закупки
                </th>
                {/* 3. Банковская гарантия (17%) */}
                <th className="text-left px-3 py-3 w-[17%]">
                  Банковская гарантия
                </th>
                {/* 4. Сумма договора (12%) */}
                <th className="text-right px-3 py-3 w-[12%]">
                  Сумма договора
                </th>
                {/* 5. Срок сдачи (8%) */}
                <th className="text-right px-3 py-3 w-[8%]">
                  Срок сдачи
                </th>
                {/* 6. Риск (7%) - С отступом от края */}
                <th className="text-center pl-2 pr-6 py-3 w-[7%]">
                  Риск
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--card-border)]">
              {filteredProjects.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-[var(--text-muted)] text-sm">
                    Объектов по выбранным критериям не найдено
                  </td>
                </tr>
              ) : (
                filteredProjects.map((project) => {
                  const currentStageIdx = getStageIndex(project.tender_stage);
                  const isRowCritical = project.risk_level === 'critical';
                  const isHighlighted = activeHighlightId === project.id;

                  return (
                    <tr
                      key={project.id}
                      id={`project-row-${project.id}`}
                      className={`transition-all duration-300 ${
                        isHighlighted
                          ? 'bg-amber-100/90 dark:bg-amber-950/70 ring-2 ring-amber-500 ring-inset shadow-md'
                          : isRowCritical
                          ? 'bg-red-50/25 dark:bg-red-950/15 hover:bg-red-50/40 dark:hover:bg-red-950/25'
                          : 'hover:bg-[var(--card-subtle)]/70'
                      }`}
                    >
                      {/* 1. Project info (21%) */}
                      <td className="px-3 py-3.5 align-middle overflow-hidden max-w-0">
                        <p className="font-semibold text-[var(--text-main)] text-sm leading-snug line-clamp-1" title={project.project_name}>
                          {project.project_name}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5 truncate text-xs">
                          <span className="font-mono text-[var(--text-muted)] shrink-0">{project.project_code}</span>
                          {project.customer_name && (
                            <span className="text-[var(--text-sub)] truncate max-w-[120px]" title={project.customer_name}>
                              · {project.customer_name}
                            </span>
                          )}
                          <span className="text-[var(--text-muted)] text-[10px]">·</span>
                          <a
                            href={project.google_drive_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] text-[var(--text-muted)] hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors shrink-0"
                            title="Открыть документы объекта в Google Диск"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <FileSpreadsheet className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                            <span>Диск</span>
                            <ExternalLink className="h-2.5 w-2.5 opacity-60" />
                          </a>
                        </div>
                        {project.curator_name && (
                          <p className="text-[11px] text-[var(--text-muted)] mt-0.5 truncate">
                            Куратор: {project.curator_name}
                          </p>
                        )}
                      </td>

                      {/* 2. Linear Stepper (35%) - Все 5 стадий с названиями */}
                      <td className="px-3 py-3.5 align-middle overflow-hidden max-w-0">
                        <div className="grid grid-cols-5 gap-1 w-full">
                          {STAGES.map((stage, idx) => {
                            const isCompleted = idx < currentStageIdx;
                            const isCurrent = idx === currentStageIdx;

                            return (
                              <button
                                key={stage.id}
                                type="button"
                                onClick={() => handleStageClick(project, stage)}
                                title={`Этап ${stage.stepNumber}: ${stage.label}. Нажмите для изменения`}
                                disabled={updatingId === project.id}
                                className={`flex flex-col items-center justify-center py-1 px-1 rounded-lg text-center transition-all cursor-pointer ${
                                  isCurrent
                                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-bold shadow-2xs ring-1 ring-slate-900 dark:ring-slate-100'
                                    : isCompleted
                                    ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 border border-emerald-200/80 dark:border-emerald-800/60'
                                    : 'bg-[var(--card-subtle)] text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)] border border-[var(--card-border)]'
                                }`}
                              >
                                <span className="text-[10px] font-mono leading-none font-bold">
                                  {isCompleted ? '✓' : stage.stepNumber}
                                </span>
                                <span className="text-[10px] font-medium leading-tight truncate w-full mt-0.5">
                                  {stage.label}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </td>

                      {/* 3. Bank Guarantee Compact Widget (17%) */}
                      <td className="px-3 py-3.5 align-middle overflow-hidden max-w-0">
                        <BankGuaranteeWidget bg={project.bank_guarantee} />
                      </td>

                      {/* 4. Contract Sum (12%) */}
                      <td className="px-3 py-3.5 text-right font-mono text-[var(--text-main)] align-middle">
                        <p className="font-bold whitespace-nowrap">{formatCurrency(project.contract_sum)}</p>
                        <div className="flex items-center justify-end gap-1.5 text-[11px] text-[var(--text-sub)] mt-0.5">
                          <span>{formatPercent(project.completion_percent || 0)}</span>
                          <span className="text-[var(--text-muted)]">КС-2</span>
                        </div>
                      </td>

                      {/* 5. Deadline & Penalties (8%) */}
                      <td className="px-3 py-3.5 text-right text-[var(--text-main)] align-middle">
                        <p className="font-medium whitespace-nowrap text-xs">
                          {project.deadline_date ? formatDate(project.deadline_date) : '—'}
                        </p>
                        {project.days_overdue > 0 ? (
                          <p className="text-[11px] text-red-600 dark:text-red-400 font-semibold whitespace-nowrap mt-0.5">
                            +{project.days_overdue} дн.
                          </p>
                        ) : (
                          <p className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-0.5 whitespace-nowrap">
                            В графике
                          </p>
                        )}
                      </td>

                      {/* 6. Risk Badge (7%) - С хорошим отступом от правого края */}
                      <td className="pl-2 pr-6 py-3.5 text-center align-middle">
                        <div className="flex items-center justify-center max-w-[80px] mx-auto">
                          {getRiskBadge(project.risk_level)}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* ============================================================ */}
        {/* MOBILE CARDS VIEW (< 768px): Responsive Compact Bento Cards   */}
        {/* ============================================================ */}
        <div className="md:hidden divide-y divide-[var(--card-border)]">
          {filteredProjects.length === 0 ? (
            <div className="p-8 text-center text-sm text-[var(--text-muted)]">
              Объектов по выбранным фильтрам не найдено
            </div>
          ) : (
            filteredProjects.map((project) => {
              const currentStageIdx = getStageIndex(project.tender_stage);
              const bg = project.bank_guarantee;
              const isBgCritical = bg && (bg.days_remaining < 5 || bg.is_critical);
              const isHighlighted = activeHighlightId === project.id;

              return (
                <div
                  key={project.id}
                  id={`project-card-${project.id}`}
                  className={`p-4 space-y-3 transition-all duration-300 ${
                    isHighlighted
                      ? 'bg-amber-100/90 dark:bg-amber-950/70 ring-2 ring-amber-500 rounded-xl shadow-md'
                      : ''
                  }`}
                >
                  {/* Top: Title & Risk badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-[var(--text-main)] text-sm">
                        {project.project_name}
                      </h3>
                      <div className="flex items-center gap-1.5 flex-wrap text-xs text-[var(--text-sub)] mt-0.5">
                        <span className="font-mono text-[var(--text-muted)]">{project.project_code}</span>
                        {project.customer_name ? <span>· {project.customer_name}</span> : ''}
                        <span>·</span>
                        <a
                          href={project.google_drive_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-emerald-700 dark:text-emerald-400 font-medium hover:underline"
                          title="Открыть документы объекта в Google Диск"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <FileSpreadsheet className="h-3 w-3" />
                          <span>Google Диск</span>
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      </div>
                    </div>
                    {getRiskBadge(project.risk_level)}
                  </div>

                  {/* Stepper in Mobile Card: 5 Equal Columns, No Overflow */}
                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-semibold text-[var(--text-muted)]">
                      Стадия закупки (нажмите для смены):
                    </span>
                    <div className="grid grid-cols-5 gap-1 w-full pt-1">
                      {STAGES.map((stage, idx) => {
                        const isCompleted = idx < currentStageIdx;
                        const isCurrent = idx === currentStageIdx;

                        return (
                          <button
                            key={stage.id}
                            type="button"
                            onClick={() => handleStageClick(project, stage)}
                            disabled={updatingId === project.id}
                            className={`flex flex-col items-center justify-center p-1.5 rounded-xl text-center transition-all cursor-pointer ${
                              isCurrent
                                ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs font-bold ring-1 ring-slate-900 dark:ring-slate-100'
                                : isCompleted
                                ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800/60'
                                : 'bg-[var(--card-subtle)] text-[var(--text-muted)] border border-[var(--card-border)]'
                            }`}
                          >
                            <span className="text-[10px] font-mono leading-none font-bold">
                              {isCompleted ? '✓' : stage.stepNumber}
                            </span>
                            <span className="text-[9px] font-medium leading-tight truncate w-full mt-0.5">
                              {stage.label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Bank Guarantee Widget Mobile */}
                  <BankGuaranteeWidget bg={bg} />

                  {/* Financial & Deadline Grid */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                      <span className="text-[10px] uppercase font-medium text-[var(--text-muted)]">Сумма договора</span>
                      <p className="text-sm font-semibold font-mono text-[var(--text-main)] mt-0.5">
                        {formatCurrency(project.contract_sum)}
                      </p>
                    </div>
                    <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                      <span className="text-[10px] uppercase font-medium text-[var(--text-muted)]">Срок сдачи</span>
                      <p className="text-sm font-medium text-[var(--text-main)] mt-0.5">
                        {project.deadline_date ? formatDate(project.deadline_date) : '—'}
                      </p>
                      {project.days_overdue > 0 && (
                        <span className="text-[11px] font-semibold text-red-600 dark:text-red-400 block mt-0.5">
                          +{project.days_overdue} дн. просрочка
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-[var(--text-sub)]">
                      <span>Выполнение работ</span>
                      <span className="font-mono font-medium text-[var(--text-main)]">{formatPercent(project.completion_percent || 0)}</span>
                    </div>
                    <div className="h-2 bg-[var(--card-subtle)] rounded-full overflow-hidden border border-[var(--card-border)]">
                      <div
                        className={`h-full rounded-full transition-all ${
                          project.risk_level === 'critical'
                            ? 'bg-red-600'
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
                    <div className="flex items-center justify-between text-xs bg-red-50 dark:bg-red-950/40 p-2.5 rounded-xl border border-red-300 dark:border-red-900/60 text-red-900 dark:text-red-200">
                      <span className="flex items-center gap-1.5 font-medium">
                        <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
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

      {/* ============================================================ */}
      {/* CONFIRMATION MODAL: Protection against accidental stage click */}
      {/* ============================================================ */}
      {pendingStageChange && (
        <ConfirmModal
          isOpen={true}
          title="Смена стадии тендера / закупки"
          description={
            <span>
              Вы действительно хотите перевести объект{' '}
              <strong className="text-[var(--text-main)]">
                «{pendingStageChange.project.project_name}»
              </strong>{' '}
              на новый этап? Это изменит контрольные сроки и регламентный чек-лист работ.
            </span>
          }
          currentStatusLabel={currentStageDef?.label || 'Текущая'}
          newStatusLabel={pendingStageChange.targetStage.label}
          confirmText="Перевести этап"
          cancelText="Отмена"
          variant="default"
          isLoading={updatingId === pendingStageChange.project.id}
          onConfirm={handleConfirmStageChange}
          onCancel={() => setPendingStageChange(null)}
        />
      )}
    </div>
  );
}
