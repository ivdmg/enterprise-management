import { useState, useEffect, useMemo, useRef } from 'react';
import {
  CheckSquare,
  Flame,
  Clock,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  User,
  Search,
  FileSpreadsheet,
  CheckCircle2,
  Building2,
  RotateCcw,
  Check,
  Download,
  AlertTriangle,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { Select } from '@/components/Select';
import { ConfirmModal } from '@/components/ConfirmModal';
import { apiClient } from '@/api/client';
import { useRole } from '@/context/RoleContext';
import { useToast } from '@/context/ToastContext';
import { formatDate, formatCurrency } from '@/utils/format';
import type { TaskItem, TaskWorkflowStatus } from '@/types';
import { ENTERPRISE_ROLES } from '@/types/roles';

type QuickFilter = 'all' | 'my' | 'urgent' | 'accounting';

const STATUS_CONFIG: Record<
  TaskWorkflowStatus,
  {
    label: string;
    variant: 'info' | 'warning' | 'success' | 'neutral' | 'danger';
    badgeClass: string;
    dotClass: string;
  }
> = {
  in_progress: {
    label: 'В работе',
    variant: 'info',
    badgeClass:
      'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700',
    dotClass: 'bg-slate-600 dark:bg-slate-400',
  },
  transferred_to_manager: {
    label: 'Передано менеджеру',
    variant: 'warning',
    badgeClass:
      'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800/60',
    dotClass: 'bg-amber-500',
  },
  approved_closed: {
    label: 'Согласовано / Закрыто',
    variant: 'success',
    badgeClass:
      'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/60',
    dotClass: 'bg-emerald-500',
  },
  pending: {
    label: 'Ожидает',
    variant: 'neutral',
    badgeClass:
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    dotClass: 'bg-slate-400',
  },
  overdue: {
    label: 'Просрочено',
    variant: 'danger',
    badgeClass:
      'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800/60',
    dotClass: 'bg-rose-500',
  },
};

const WORKFLOW_OPTIONS: { status: TaskWorkflowStatus; label: string }[] = [
  { status: 'in_progress', label: 'В работе' },
  { status: 'transferred_to_manager', label: 'Передано менеджеру' },
  { status: 'approved_closed', label: 'Согласовано / Закрыто' },
];

export function TasksTab() {
  const { activeRole, currentRoleDef } = useRole();
  const { showToast } = useToast();

  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // Mobile Accordion state: set of expanded task IDs (FE-5.2)
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(new Set());

  // ConfirmModal state for task workflow status change (FE-5.1)
  const [pendingStatusChange, setPendingStatusChange] = useState<{
    task: TaskItem;
    targetStatus: TaskWorkflowStatus;
  } | null>(null);

  // Close dropdown on outside click
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as HTMLElement;
      if (!target.closest('.tasks-status-dropdown-container')) {
        setActiveDropdownId(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch tasks on mount
  useEffect(() => {
    let mounted = true;
    apiClient
      .getTasks()
      .then((data) => {
        if (mounted) setTasks(data);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  // Request status change (opens ConfirmModal)
  const requestStatusChange = (task: TaskItem, newStatus: TaskWorkflowStatus) => {
    if (task.status === newStatus) {
      setActiveDropdownId(null);
      return;
    }
    setActiveDropdownId(null);
    setPendingStatusChange({ task, targetStatus: newStatus });
  };

  // Confirmed status change in modal
  const handleConfirmStatusChange = async () => {
    if (!pendingStatusChange) return;
    const { task, targetStatus } = pendingStatusChange;
    const taskId = task.id;

    setUpdatingId(taskId);
    setPendingStatusChange(null);
    const previousTasks = [...tasks];

    // Optimistic update
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: targetStatus } : t))
    );

    const statusLabel = STATUS_CONFIG[targetStatus]?.label || targetStatus;
    showToast(`Статус задачи обновлен: «${statusLabel}»`, 'success');

    try {
      await apiClient.updateTaskStatus(taskId, targetStatus);
    } catch {
      setTasks(previousTasks);
      showToast('Ошибка при обновлении статуса задачи на сервере', 'error');
    } finally {
      setUpdatingId(null);
    }
  };

  // Toggle mobile accordion card
  const toggleTaskExpand = (id: string) => {
    setExpandedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Manager action for accounting task
  const handleMarkDeliveredToCustomer = async (taskId: string) => {
    const task = tasks.find((t) => t.id === taskId);
    if (task) {
      requestStatusChange(task, 'approved_closed');
    }
  };

  // Options for custom Role Select (FE-5.1)
  const roleSelectOptions = useMemo(() => {
    return [
      { value: 'all', label: 'Все 9 ролей предприятия' },
      ...ENTERPRISE_ROLES.map((r) => ({ value: r.id, label: r.name })),
    ];
  }, []);

  // Filtered task items
  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      // Quick filter
      if (quickFilter === 'my') {
        if (task.responsible_role !== activeRole) return false;
      } else if (quickFilter === 'urgent') {
        const isUrgent =
          (task.days_remaining !== undefined && task.days_remaining <= 5) ||
          task.is_urgent;
        if (!isUrgent) return false;
      } else if (quickFilter === 'accounting') {
        if (task.source !== 'accounting') return false;
      }

      // Role filter
      if (roleFilter !== 'all') {
        if (task.responsible_role !== roleFilter) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const inTitle = task.task_title.toLowerCase().includes(q);
        const inDesc = task.description?.toLowerCase().includes(q) || false;
        const inContract = task.related_contract?.toLowerCase().includes(q) || false;
        const inPerson = task.responsible_person?.toLowerCase().includes(q) || false;
        if (!inTitle && !inDesc && !inContract && !inPerson) return false;
      }

      return true;
    });
  }, [tasks, quickFilter, roleFilter, searchQuery, activeRole]);

  // Statistics
  const totalCount = tasks.length;
  const myCount = tasks.filter((t) => t.responsible_role === activeRole).length;
  const urgentCount = tasks.filter(
    (t) => (t.days_remaining !== undefined && t.days_remaining <= 5) || t.is_urgent
  ).length;
  const accountingCount = tasks.filter((t) => t.source === 'accounting').length;
  const accountingPendingTasks = tasks.filter(
    (t) => t.source === 'accounting' && t.status === 'transferred_to_manager'
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const pendingItemStatusLabel = pendingStatusChange
    ? STATUS_CONFIG[pendingStatusChange.task.status]?.label
    : '';
  const pendingTargetStatusLabel = pendingStatusChange
    ? STATUS_CONFIG[pendingStatusChange.targetStatus]?.label
    : '';

  return (
    <div className="space-y-4" id="tasks-tab-section">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-main)] flex items-center gap-2">
            <CheckSquare className="h-5 w-5 text-[var(--text-main)]" />
            Смарт-реестр операционных задач
          </h2>
          <p className="text-xs text-[var(--text-sub)]">
            Сквозной контроль чек-листов, интеграция с Google Диском и защита от срыва регламентов
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-sub)]">
            Активная роль: <strong className="text-[var(--text-main)]">{currentRoleDef.shortName}</strong>
          </span>
          <span className="text-xs text-[var(--text-muted)]">·</span>
          <span className="text-xs font-mono font-semibold text-[var(--text-main)]">
            {filteredTasks.length} из {totalCount} задач
          </span>
        </div>
      </div>

      {/* Accounting Pending Alert Box */}
      {accountingPendingTasks.length > 0 && (
        <div className="bg-amber-50/75 dark:bg-amber-950/30 border border-amber-200/90 dark:border-amber-900/50 rounded-2xl p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-amber-500/15 text-amber-700 dark:text-amber-400 shrink-0">
                <FileSpreadsheet className="h-4.5 w-4.5" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-bold text-amber-900 dark:text-amber-200 leading-snug">
                    Требуется согласование отчетов с заказчиком
                  </h3>
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-200/90 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200 shrink-0">
                    {accountingPendingTasks.length} новых
                  </span>
                </div>
                <p className="text-xs text-amber-800/80 dark:text-amber-300/80">
                  Бухгалтерия загрузила отчеты по взаиморасчетам. Требуется согласование с заказчиком по объекту.
                </p>
              </div>
            </div>

            {activeRole === 'manager' && (
              <span className="text-[11px] font-semibold text-amber-900 dark:text-amber-200 bg-amber-100/70 dark:bg-amber-900/40 px-2.5 py-1 rounded-xl shrink-0">
                Ваша зона ответственности (Менеджер)
              </span>
            )}
          </div>

          {/* List of pending accounting documents (border removed) */}
          <div className="space-y-2 pt-1">
            {accountingPendingTasks.map((t) => (
              <div
                key={t.id}
                className="bg-[var(--card-bg)] rounded-xl border-0 shadow-xs p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-[var(--text-main)]">
                      {t.task_title}
                    </span>
                    {t.related_contract && (
                      <span className="text-[11px] font-mono text-[var(--text-sub)] bg-[var(--card-subtle)] px-1.5 py-0.5 rounded border border-[var(--card-border)]">
                        {t.related_contract}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--text-sub)] line-clamp-2">
                    {t.description}
                  </p>
                  <p className="text-[11px] text-[var(--text-muted)] flex items-center gap-1.5">
                    <Clock className="h-3 w-3" />
                    <span>
                      Срок согласования: <strong className="text-[var(--text-main)]">{formatDate(t.due_date)}</strong>
                    </span>
                    {t.responsible_person && <span>· Ответственный: {t.responsible_person}</span>}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {t.google_drive_link && (
                    <a
                      href={t.google_drive_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-h-[38px] px-3 py-1.5 rounded-xl bg-[var(--card-subtle)] hover:bg-[var(--card-border)] text-[var(--text-main)] text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer border border-[var(--card-border)]"
                      title="Открыть и скачать файл из Google Диска"
                    >
                      <Download className="h-3.5 w-3.5 text-[var(--text-sub)]" />
                      <span>Скачать файл</span>
                      <ExternalLink className="h-3 w-3 text-[var(--text-muted)]" />
                    </a>
                  )}

                  <button
                    type="button"
                    onClick={() => handleMarkDeliveredToCustomer(t.id)}
                    className="min-h-[38px] px-3.5 py-1.5 rounded-xl bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
                    id={`delivered-btn-${t.id}`}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Отметить: Передано заказчику</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Control Bar: Quick Filter Pills & Custom Role Selector (FE-5.1) */}
      <Card padding="sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* Quick Filter Tabs (White & Gray Bento) */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none pb-1 lg:pb-0">
            <button
              type="button"
              onClick={() => setQuickFilter('all')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
                quickFilter === 'all'
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
              }`}
              id="filter-all-tasks"
            >
              <span>Все задачи</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-black/10 dark:bg-white/20">
                {totalCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setQuickFilter('my')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
                quickFilter === 'my'
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
              }`}
              id="filter-my-tasks"
            >
              <User className="h-3.5 w-3.5" />
              <span>Мои задачи ({currentRoleDef.shortName})</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-black/10 dark:bg-white/20">
                {myCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setQuickFilter('urgent')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
                quickFilter === 'urgent'
                  ? 'bg-rose-600 text-white font-semibold shadow-2xs'
                  : 'bg-rose-500/10 text-rose-700 dark:text-rose-400 hover:bg-rose-500/20'
              }`}
              id="filter-urgent-tasks"
            >
              <Flame className="h-3.5 w-3.5" />
              <span>Горящие (&le; 5 дн.)</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-200 dark:bg-rose-900/60 text-rose-900 dark:text-rose-200">
                {urgentCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setQuickFilter('accounting')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
                quickFilter === 'accounting'
                  ? 'bg-amber-600 text-white font-semibold shadow-2xs'
                  : 'bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20'
              }`}
              id="filter-accounting-tasks"
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              <span>От бухгалтерии</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-200 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200">
                {accountingCount}
              </span>
            </button>
          </div>

          {/* Search Bar & Custom Role Select (FE-5.1) */}
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            {/* Search input */}
            <div className="relative flex-1 sm:w-60">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-muted)] pointer-events-none" />
              <input
                type="text"
                placeholder="Поиск по задачам..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-[var(--card-subtle)] border border-[var(--card-border)] rounded-xl text-[var(--text-main)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] min-h-[38px]"
              />
            </div>

            {/* Custom Styled Role Select Component (FE-5.1) */}
            <div className="w-full sm:w-56">
              <Select
                options={roleSelectOptions}
                value={roleFilter}
                onChange={setRoleFilter}
                size="md"
                className="w-full"
                id="tasks-role-filter-select"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Task List / Smart Register Table */}
      <Card padding="none">
        {filteredTasks.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <CheckCircle2 className="h-8 w-8 text-[var(--text-muted)] mx-auto" />
            <p className="text-sm font-semibold text-[var(--text-main)]">
              Задач по выбранным фильтрам не найдено
            </p>
            <p className="text-xs text-[var(--text-sub)]">
              Попробуйте сбросить фильтры или изменить поисковый запрос
            </p>
            <button
              type="button"
              onClick={() => {
                setQuickFilter('all');
                setRoleFilter('all');
                setSearchQuery('');
              }}
              className="mt-2 px-3 py-1.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] text-xs text-[var(--text-main)] font-medium hover:bg-[var(--card-bg)] transition-colors cursor-pointer"
            >
              Сбросить фильтры
            </button>
          </div>
        ) : (
          <>
            {/* ============================================================ */}
            {/* DESKTOP TABLE VIEW (>= 768px): Zebra striping & contrast (FE-1.5) */}
            {/* Proportions: Задача 30%, Объект 18%, Ответственный 14%, Срок/Штраф 14%, Статус 16%, Документ 8% */}
            {/* ============================================================ */}
            <div className="hidden md:block overflow-x-hidden">
              <table className="w-full text-sm table-fixed" id="tasks-desktop-table">
                <thead>
                  <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)] text-xs text-[var(--text-sub)] uppercase font-semibold">
                    <th className="text-left px-3 py-3 w-[30%]">Задача</th>
                    <th className="text-left px-3 py-3 w-[18%]">Объект / Договор</th>
                    <th className="text-left px-3 py-3 w-[14%]">Ответственный</th>
                    <th className="text-right px-3 py-3 w-[14%]">Срок и штраф</th>
                    <th className="text-center px-3 py-3 w-[16%] min-w-[170px]">Статус</th>
                    <th className="text-right px-3 py-3 w-[8%]">Файл</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--card-border)]">
                  {filteredTasks.map((task, idx) => {
                    const statusInfo = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                    const isDropdownOpen = activeDropdownId === task.id;
                    const isUrgent =
                      (task.days_remaining !== undefined && task.days_remaining <= 5) ||
                      task.is_urgent;
                    const isEven = idx % 2 === 1;

                    return (
                      <tr
                        key={task.id}
                        className={`transition-colors ${
                          isUrgent
                            ? 'bg-rose-50/20 dark:bg-rose-950/10 hover:bg-rose-50/35 dark:hover:bg-rose-950/20'
                            : isEven
                            ? 'bg-[var(--card-subtle)]/40 hover:bg-[var(--card-subtle)]/80'
                            : 'bg-[var(--card-bg)] hover:bg-[var(--card-subtle)]/60'
                        }`}
                      >
                        {/* Task Title (30%) */}
                        <td className="px-3 py-3.5 align-middle">
                          <div className="space-y-0.5 min-w-0">
                            <p className="font-semibold text-[var(--text-main)] text-sm leading-snug line-clamp-2" title={task.task_title}>
                              {task.task_title}
                            </p>
                            {task.description && (
                              <p className="text-xs text-[var(--text-sub)] line-clamp-1 truncate" title={task.description}>
                                {task.description}
                              </p>
                            )}
                          </div>
                        </td>

                        {/* Contract / Project (18%) */}
                        <td className="px-3 py-3.5 align-middle text-xs">
                          {task.related_contract ? (
                            <span className="font-mono text-[var(--text-main)] font-medium truncate block" title={task.related_contract}>
                              {task.related_contract}
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </td>

                        {/* Responsible (14%) */}
                        <td className="px-3 py-3.5 align-middle text-xs">
                          <span className="font-medium text-[var(--text-main)] truncate block" title={task.responsible_person || '—'}>
                            {task.responsible_person || '—'}
                          </span>
                        </td>

                        {/* Due Date & Penalties (14%) */}
                        <td className="px-3 py-3.5 align-middle text-right text-xs whitespace-nowrap">
                          <p className="font-medium text-[var(--text-main)]">
                            {formatDate(task.due_date)}
                          </p>
                          {task.estimated_penalty_amount && task.estimated_penalty_amount > 0 ? (
                            <span className="font-mono font-bold text-rose-600 dark:text-rose-400 block mt-0.5 text-[11px]">
                              Штраф: {formatCurrency(task.estimated_penalty_amount)}
                            </span>
                          ) : task.days_remaining !== undefined ? (
                            <span
                              className={`text-[11px] font-semibold block mt-0.5 ${
                                task.days_remaining <= 2
                                  ? 'text-rose-600 dark:text-rose-400'
                                  : task.days_remaining <= 5
                                  ? 'text-amber-600 dark:text-amber-400'
                                  : 'text-[var(--text-muted)]'
                              }`}
                            >
                              {task.days_remaining < 0
                                ? `-${Math.abs(task.days_remaining)} дн.`
                                : task.days_remaining === 0
                                ? 'Сегодня'
                                : `${task.days_remaining} дн.`}
                            </span>
                          ) : null}
                        </td>

                        {/* Status Dropdown with ConfirmModal Protection (16%) (FE-1.5) */}
                        <td className="px-3 py-3.5 align-middle text-center">
                          <div className="relative inline-block w-full max-w-[170px] text-left tasks-status-dropdown-container">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveDropdownId(isDropdownOpen ? null : task.id);
                              }}
                              disabled={updatingId === task.id}
                              className={`w-full px-2.5 py-1.5 rounded-xl border text-xs font-semibold flex items-center justify-between gap-1.5 cursor-pointer shadow-2xs transition-all overflow-hidden ${statusInfo.badgeClass}`}
                            >
                              <span className="flex items-center gap-1.5 min-w-0 truncate">
                                <span className={`h-2 w-2 rounded-full shrink-0 ${statusInfo.dotClass}`} />
                                <span className="truncate whitespace-nowrap">{statusInfo.label}</span>
                              </span>
                              <ChevronDown className="h-3 w-3 shrink-0 opacity-70" />
                            </button>

                            {/* Dropdown Menu */}
                            {isDropdownOpen && (
                              <div className="absolute right-0 mt-1.5 w-52 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl shadow-xl py-1.5 z-40 text-left animate-in fade-in zoom-in-95 duration-100">
                                <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--card-border)]">
                                  Сменить статус:
                                </p>
                                {WORKFLOW_OPTIONS.map((opt) => {
                                  const optConfig = STATUS_CONFIG[opt.status];
                                  const isCurrent = task.status === opt.status;

                                  return (
                                    <button
                                      key={opt.status}
                                      type="button"
                                      onClick={() => requestStatusChange(task, opt.status)}
                                      className={`w-full px-3 py-2 text-xs flex items-center justify-between hover:bg-[var(--card-subtle)] transition-colors cursor-pointer ${
                                        isCurrent
                                          ? 'font-bold text-[var(--text-main)] bg-[var(--card-subtle)]'
                                          : 'text-[var(--text-sub)]'
                                      }`}
                                    >
                                      <div className="flex items-center gap-2">
                                        <span className={`w-2 h-2 rounded-full ${optConfig.dotClass}`} />
                                        <span>{optConfig.label}</span>
                                      </div>
                                      {isCurrent && (
                                        <Check className="h-3.5 w-3.5 text-[var(--text-main)] shrink-0" />
                                      )}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Document Link (8%) */}
                        <td className="px-3 py-3.5 align-middle text-right text-xs">
                          {task.document_name ? (
                            <a
                              href={task.google_drive_link || '#'}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center justify-center p-1.5 rounded-lg border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-border)] text-[var(--text-main)] transition-colors"
                              title={`Открыть: ${task.document_name}`}
                            >
                              <FileSpreadsheet className="h-3.5 w-3.5 text-[var(--text-sub)]" />
                            </a>
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ============================================================ */}
            {/* MOBILE CARDS VIEW (< 768px): Accordion Cards (FE-5.2)        */}
            {/* ============================================================ */}
            <div className="md:hidden divide-y divide-[var(--card-border)]" id="smart-tasks-mobile-list">
              {filteredTasks.map((task) => {
                const statusInfo = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                const isUrgent =
                  (task.days_remaining !== undefined && task.days_remaining <= 5) ||
                  task.is_urgent;
                const isExpanded = expandedTaskIds.has(task.id);

                return (
                  <div key={task.id} className="p-3.5 transition-colors">
                    {/* Collapsed Header: Tap to expand */}
                    <div
                      onClick={() => toggleTaskExpand(task.id)}
                      className="flex items-start justify-between gap-2.5 cursor-pointer select-none"
                      role="button"
                      tabIndex={0}
                    >
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-[var(--text-main)] text-sm leading-snug line-clamp-1">
                            {task.task_title}
                          </h4>
                        </div>
                        <p className="text-xs text-[var(--text-sub)] truncate">
                          {task.related_contract || 'Без привязки к договору'}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                          <span>{task.responsible_person}</span>
                          <span>·</span>
                          <span>до {formatDate(task.due_date)}</span>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1.5 shrink-0">
                        <span className={`px-2 py-0.5 rounded-lg border text-[11px] font-semibold flex items-center gap-1 ${statusInfo.badgeClass}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${statusInfo.dotClass}`} />
                          <span>{statusInfo.label}</span>
                        </span>
                        {isUrgent && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60">
                            &le; {task.days_remaining} дн.
                          </span>
                        )}
                        <div className="p-0.5 text-[var(--text-muted)]">
                          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </div>
                      </div>
                    </div>

                    {/* Expanded Accordion Body (FE-5.2) */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-[var(--card-border)] space-y-3 animate-in fade-in duration-150">
                        {task.description && (
                          <p className="text-xs text-[var(--text-sub)] leading-relaxed bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                            {task.description}
                          </p>
                        )}

                        {/* Meta info grid */}
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                            <span className="text-[10px] text-[var(--text-muted)] block uppercase font-medium">
                              Ответственный куратор
                            </span>
                            <span className="font-semibold text-[var(--text-main)] mt-0.5 block truncate">
                              {task.responsible_person || '—'}
                            </span>
                          </div>
                          <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                            <span className="text-[10px] text-[var(--text-muted)] block uppercase font-medium">
                              Срок исполнения
                            </span>
                            <span className="font-semibold text-[var(--text-main)] mt-0.5 block">
                              {formatDate(task.due_date)}
                            </span>
                            {task.days_remaining !== undefined && (
                              <span className="text-[10px] text-rose-600 dark:text-rose-400 block mt-0.5">
                                {task.days_remaining < 0
                                  ? `Просрочка ${Math.abs(task.days_remaining)} дн.`
                                  : `Осталось ${task.days_remaining} дн.`}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Document link on mobile */}
                        {task.document_name && (
                          <a
                            href={task.google_drive_link || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="min-h-[44px] w-full px-3 py-2 rounded-xl bg-[var(--card-subtle)] border border-[var(--card-border)] text-[var(--text-main)] text-xs font-medium flex items-center justify-between"
                          >
                            <span className="flex items-center gap-2 truncate">
                              <FileSpreadsheet className="h-4 w-4 shrink-0 text-[var(--text-muted)]" />
                              <span className="truncate">{task.document_name}</span>
                            </span>
                            <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
                          </a>
                        )}

                        {/* Mobile Status Buttons with ConfirmModal Protection (FE-5.2) */}
                        <div className="pt-2 border-t border-[var(--card-border)] space-y-1.5">
                          <span className="text-[10px] text-[var(--text-muted)] uppercase font-semibold tracking-wider">
                            Сменить статус (защита подтверждением):
                          </span>
                          <div className="grid grid-cols-3 gap-1.5">
                            {WORKFLOW_OPTIONS.map((opt) => {
                              const isCurrent = task.status === opt.status;
                              return (
                                <button
                                  key={opt.status}
                                  type="button"
                                  onClick={() => requestStatusChange(task, opt.status)}
                                  className={`min-h-[44px] px-2 py-1.5 rounded-xl text-[11px] font-semibold border flex items-center justify-center text-center transition-all cursor-pointer ${
                                    isCurrent
                                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs border-slate-900 dark:border-slate-100'
                                      : 'border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
                                  }`}
                                >
                                  {opt.label === 'В работе'
                                    ? 'В работе'
                                    : opt.label === 'Передано менеджеру'
                                    ? 'Менеджеру'
                                    : 'Закрыто'}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Card>

      {/* ============================================================ */}
      {/* CONFIRMATION MODAL: Protection against accidental status changes (FE-5.1) */}
      {/* ============================================================ */}
      {pendingStatusChange && (
        <ConfirmModal
          isOpen={true}
          title="Смена статуса задачи"
          description={
            <span>
              Вы действительно хотите изменить статус задачи{' '}
              <strong className="text-[var(--text-main)]">
                «{pendingStatusChange.task.task_title}»
              </strong>
              {pendingStatusChange.task.related_contract
                ? ` по объекту ${pendingStatusChange.task.related_contract}`
                : ''}
              ?
            </span>
          }
          currentStatusLabel={pendingItemStatusLabel}
          newStatusLabel={pendingTargetStatusLabel}
          confirmText="Подтвердить смену"
          cancelText="Отмена"
          variant="default"
          isLoading={updatingId === pendingStatusChange.task.id}
          onConfirm={handleConfirmStatusChange}
          onCancel={() => setPendingStatusChange(null)}
        />
      )}
    </div>
  );
}
