import { useState, useMemo } from 'react';
import {
  Flame,
  AlertTriangle,
  ArrowUpRight,
  ArrowLeft,
  Clock,
  User,
  Building2,
  Scale,
  ShieldAlert,
  FileText,
  DollarSign,
  Search,
  RotateCcw,
  SlidersHorizontal,
} from 'lucide-react';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { Select } from '@/components/Select';
import { formatDate, formatCurrency } from '@/utils/format';
import type { FireItem } from '@/types';

export interface FireDetailViewProps {
  items: FireItem[];
  initialCategory?: 'all' | 'critical' | 'warning' | 'penalties';
  onBack: () => void;
  onNavigateToProject?: (projectId: string) => void;
  onNavigateTab?: (tabId: string) => void;
}

export function FireDetailView({
  items,
  initialCategory = 'all',
  onBack,
  onNavigateToProject,
  onNavigateTab,
}: FireDetailViewProps) {
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'critical' | 'warning' | 'penalties'>(initialCategory);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProject, setSelectedProject] = useState('all');
  const [selectedResponsible, setSelectedResponsible] = useState('all');
  const [sortBy, setSortBy] = useState<'severity' | 'financial_desc' | 'due_date_asc'>('severity');

  // Counts for pills
  const criticalCount = items.filter((i) => i.severity === 'CRITICAL').length;
  const warningCount = items.filter((i) => i.severity === 'WARNING').length;
  const penaltiesCount = items.filter((i) => (i.penalty_amount || 0) > 0 || (i.days_overdue || 0) > 0).length;

  // Unique projects options
  const projectOptions = useMemo(() => {
    const projectsMap = new Map<string, string>();
    items.forEach((item) => {
      if (item.project_name) {
        projectsMap.set(item.project_name, item.project_name);
      }
    });
    const opts = [{ value: 'all', label: 'Все объекты строительства' }];
    projectsMap.forEach((name) => {
      opts.push({ value: name, label: name });
    });
    return opts;
  }, [items]);

  // Unique responsible persons options
  const responsibleOptions = useMemo(() => {
    const respSet = new Set<string>();
    items.forEach((item) => {
      if (item.responsible) respSet.add(item.responsible);
    });
    const opts = [{ value: 'all', label: 'Все ответственные лица' }];
    respSet.forEach((name) => {
      opts.push({ value: name, label: name });
    });
    return opts;
  }, [items]);

  const sortOptions = [
    { value: 'severity', label: 'По уровню критичности' },
    { value: 'financial_desc', label: 'По сумме риска (убывание)' },
    { value: 'due_date_asc', label: 'По сроку (сначала ближайшие)' },
  ];

  // Filtered & sorted items
  const filteredItems = useMemo(() => {
    let result = items.filter((item) => {
      // Category filter
      if (categoryFilter === 'critical' && item.severity !== 'CRITICAL') return false;
      if (categoryFilter === 'warning' && item.severity !== 'WARNING') return false;
      if (categoryFilter === 'penalties' && !((item.penalty_amount || 0) > 0 || (item.days_overdue || 0) > 0)) {
        return false;
      }

      // Project filter
      if (selectedProject !== 'all' && item.project_name !== selectedProject) {
        return false;
      }

      // Responsible filter
      if (selectedResponsible !== 'all' && item.responsible !== selectedResponsible) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const inTitle = item.title.toLowerCase().includes(q);
        const inDesc = item.description.toLowerCase().includes(q);
        const inProj = (item.project_name || '').toLowerCase().includes(q);
        const inResp = item.responsible.toLowerCase().includes(q);
        if (!inTitle && !inDesc && !inProj && !inResp) return false;
      }

      return true;
    });

    // Sorting
    result = [...result].sort((a, b) => {
      if (sortBy === 'financial_desc') {
        const aVal = a.penalty_amount || a.financial_impact || 0;
        const bVal = b.penalty_amount || b.financial_impact || 0;
        return bVal - aVal;
      }
      if (sortBy === 'due_date_asc') {
        return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
      }
      // default severity
      const severityScore = (s: string) => (s === 'CRITICAL' ? 3 : s === 'WARNING' ? 2 : 1);
      return severityScore(b.severity) - severityScore(a.severity);
    });

    return result;
  }, [items, categoryFilter, selectedProject, selectedResponsible, searchQuery, sortBy]);

  // Aggregate totals of current filtered view
  const currentTotalFinancial = filteredItems.reduce(
    (acc, item) => acc + (item.financial_impact || 0) + (item.penalty_amount || 0),
    0
  );

  const handleActionClick = (item: FireItem) => {
    if (item.project_id && onNavigateToProject) {
      onNavigateToProject(item.project_id);
    } else if (onNavigateTab) {
      onNavigateTab('tenders');
    }
  };

  const getItemCategoryIcon = (category?: string, severity?: string) => {
    const iconClass = 'h-4 w-4 shrink-0';
    switch (category) {
      case 'ks2_delay':
        return <AlertTriangle className={iconClass} />;
      case 'bank_guarantee':
        return <ShieldAlert className={iconClass} />;
      case 'disagreement_protocol':
        return <Scale className={iconClass} />;
      case 'receivable_debt':
        return <DollarSign className={iconClass} />;
      default:
        return severity === 'CRITICAL' ? (
          <Flame className={iconClass} />
        ) : (
          <AlertTriangle className={iconClass} />
        );
    }
  };

  const getCategoryTitle = () => {
    switch (categoryFilter) {
      case 'critical':
        return 'Критические риски (дедлайн ≤ 3 дней)';
      case 'warning':
        return 'Внимание и предупреждения (дедлайн 4-5 дней)';
      case 'penalties':
        return 'Штрафы и просрочки обязательств (44-ФЗ)';
      default:
        return 'Все оперативные события под риском';
    }
  };

  const resetFilters = () => {
    setCategoryFilter('all');
    setSearchQuery('');
    setSelectedProject('all');
    setSelectedResponsible('all');
    setSortBy('severity');
  };

  const hasActiveCustomFilters =
    searchQuery.trim() !== '' ||
    selectedProject !== 'all' ||
    selectedResponsible !== 'all' ||
    sortBy !== 'severity';

  const categorySelectOptions = [
    { value: 'all', label: `Все риски (${items.length})` },
    { value: 'critical', label: `Критические (${criticalCount})` },
    { value: 'warning', label: `Внимание (${warningCount})` },
    { value: 'penalties', label: `Штрафы и просрочки (${penaltiesCount})` },
  ];

  return (
    <div className="space-y-4" id="fire-detail-view-container">
      {/* Top Card Re-structured into 4 Layers */}
      <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] space-y-3.5">
        {/* Layer 1: Header with compact Back Arrow + Title */}
        <div className="flex items-center gap-3" id="fire-detail-header-layer">
          <button
            type="button"
            onClick={onBack}
            className="h-9 w-9 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-bg)] text-[var(--text-main)] flex items-center justify-center shrink-0 cursor-pointer transition-colors shadow-2xs"
            title="Назад к сводке"
            id="fire-detail-back-btn"
          >
            <ArrowLeft className="h-4.5 w-4.5" />
          </button>
          <h2 className="text-base sm:text-lg font-bold text-[var(--text-main)] leading-snug">
            {getCategoryTitle()}
          </h2>
        </div>

        {/* Layer 2: Description + Counter badge + Financial volume */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-[var(--card-border)]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--card-subtle)] text-[var(--text-main)] border border-[var(--card-border)] shrink-0">
              {filteredItems.length} из {items.length}
            </span>
            <p className="text-xs text-[var(--text-sub)]">
              Детальный реестр инцидентов с привязкой к договорам, суммам и кураторам
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--card-subtle)] border border-[var(--card-border)] self-start sm:self-auto shrink-0">
            <DollarSign className="h-4 w-4 text-red-700 dark:text-red-300 shrink-0" />
            <div className="text-left leading-tight">
              <span className="text-[10px] text-[var(--text-sub)] uppercase tracking-wider block font-medium">
                Финансовый объем:
              </span>
              <span className="font-mono font-bold text-xs sm:text-sm text-[var(--text-main)]">
                {formatCurrency(currentTotalFinancial)}
              </span>
            </div>
          </div>
        </div>

        {/* Layer 3: Statuses Filter (Dropdown on Mobile, Pills on Desktop) */}
        <div className="pt-2 border-t border-[var(--card-border)]">
          {/* Mobile Dropdown (< md) */}
          <div className="md:hidden">
            <label className="text-[11px] font-medium text-[var(--text-sub)] block mb-1">
              Фильтр по категориям рисков:
            </label>
            <Select
              options={categorySelectOptions}
              value={categoryFilter}
              onChange={(val) => setCategoryFilter(val as any)}
              size="md"
              className="w-full"
              id="fire-detail-category-select-mobile"
            />
          </div>

          {/* Desktop Pills (>= md) */}
          <div className="hidden md:flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setCategoryFilter('all')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                categoryFilter === 'all'
                  ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
              }`}
            >
              Все ({items.length})
            </button>
            <button
              type="button"
              onClick={() => setCategoryFilter('critical')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                categoryFilter === 'critical'
                  ? 'bg-red-600 text-white shadow-2xs'
                  : 'bg-red-50 text-red-800 dark:bg-red-950/60 dark:text-red-300 hover:bg-red-100 border border-red-200 dark:border-red-900/50'
              }`}
            >
              Критические ({criticalCount})
            </button>
            <button
              type="button"
              onClick={() => setCategoryFilter('warning')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                categoryFilter === 'warning'
                  ? 'bg-amber-600 text-white shadow-2xs'
                  : 'bg-amber-50 text-amber-900 dark:bg-amber-950/60 dark:text-amber-300 hover:bg-amber-100 border border-amber-200 dark:border-amber-900/50'
              }`}
            >
              Внимание ({warningCount})
            </button>
            <button
              type="button"
              onClick={() => setCategoryFilter('penalties')}
              className={`min-h-[36px] px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                categoryFilter === 'penalties'
                  ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
              }`}
            >
              Штрафы и просрочки ({penaltiesCount})
            </button>
          </div>
        </div>

        {/* Drill-Down Filters & Search Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-2 border-t border-[var(--card-border)]">
          {/* Search Input */}
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Поиск по названию или тексту..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-main)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] min-h-[38px] transition-colors"
            />
          </div>

          {/* Project Filter */}
          <Select
            options={projectOptions}
            value={selectedProject}
            onChange={setSelectedProject}
            size="md"
            className="w-full"
            id="fire-detail-project-select"
          />

          {/* Responsible Filter */}
          <Select
            options={responsibleOptions}
            value={selectedResponsible}
            onChange={setSelectedResponsible}
            size="md"
            className="w-full"
            id="fire-detail-responsible-select"
          />

          {/* Sort By */}
          <div className="flex items-center gap-1.5">
            <Select
              options={sortOptions}
              value={sortBy}
              onChange={(val) => setSortBy(val as any)}
              size="md"
              className="flex-1"
              id="fire-detail-sort-select"
            />
            {hasActiveCustomFilters && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={resetFilters}
                className="shrink-0 text-xs px-2.5 min-h-[38px] text-[var(--text-sub)] hover:text-[var(--text-main)]"
                title="Сбросить все фильтры"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Cards Grid */}
      {filteredItems.length === 0 ? (
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-10 text-center space-y-3">
          <div className="h-10 w-10 mx-auto rounded-full bg-[var(--card-subtle)] text-[var(--text-muted)] flex items-center justify-center">
            <SlidersHorizontal className="h-5 w-5" />
          </div>
          <p className="text-sm font-semibold text-[var(--text-main)]">
            Нет инцидентов, соответствующих выбранным критериям
          </p>
          <p className="text-xs text-[var(--text-sub)] max-w-sm mx-auto">
            Попробуйте изменить категорию, сбросить поисковый запрос или выбрать другой объект
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={resetFilters}>
            Сбросить фильтры
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5" id="fire-detail-cards-grid">
          {filteredItems.map((item) => {
            const isCritical = item.severity === 'CRITICAL';
            const hasPenalty = (item.penalty_amount || 0) > 0;
            const isOverdue = (item.days_overdue || 0) > 0;

            return (
              <div
                key={item.id}
                className={`rounded-2xl border border-l-4 p-5 transition-all flex flex-col justify-between gap-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] ${
                  isCritical
                    ? 'border-l-red-600 bg-red-50/60 border-red-200/90 hover:bg-red-50 dark:bg-red-950/30 dark:border-red-900/60 dark:hover:bg-red-950/40'
                    : 'border-l-amber-500 bg-amber-50/60 border-amber-200/90 hover:bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900/60 dark:hover:bg-amber-950/40'
                }`}
              >
                {/* Card Top: Severity Badge, Title, Category Icon */}
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={isCritical ? 'danger' : 'warning'}>
                        <span className="flex items-center gap-1 font-medium">
                          {getItemCategoryIcon(item.category, item.severity)}
                          <span>{isCritical ? 'Критический риск' : 'Внимание'}</span>
                        </span>
                      </Badge>

                      {isOverdue && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200 border border-red-300 dark:border-red-800">
                          Просрочка +{item.days_overdue} дн.
                        </span>
                      )}

                      {!isOverdue && item.days_remaining !== undefined && item.days_remaining > 0 && (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-200 border border-amber-300 dark:border-amber-800">
                          Осталось {item.days_remaining} дн.
                        </span>
                      )}
                    </div>

                    {item.project_name && (
                      <span className="text-[11px] font-medium text-[var(--text-sub)] flex items-center gap-1 shrink-0">
                        <Building2 className="h-3 w-3" />
                        <span className="max-w-[140px] truncate">{item.project_name}</span>
                      </span>
                    )}
                  </div>

                  {/* Title and Description */}
                  <div>
                    <h3 className="text-sm sm:text-base font-bold text-[var(--text-main)] leading-snug">
                      {item.title}
                    </h3>
                    <p className="text-xs sm:text-sm text-[var(--text-sub)] mt-1 leading-relaxed">
                      {item.description}
                    </p>
                  </div>

                  {/* Financial Impact / Penalty Box */}
                  {(item.financial_impact > 0 || hasPenalty) && (
                    <div
                      className={`flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl border text-xs ${
                        isCritical
                          ? 'bg-red-100/70 dark:bg-red-900/50 border-red-300 dark:border-red-800/60'
                          : 'bg-amber-100/70 dark:bg-amber-900/50 border-amber-300 dark:border-amber-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 text-[var(--text-sub)]">
                        <FileText className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                        <span>{hasPenalty ? 'Расчетный штраф (44-ФЗ):' : 'Финансовый объем риска:'}</span>
                      </div>
                      <span className="font-mono font-bold text-red-700 dark:text-red-300 text-sm">
                        {formatCurrency(hasPenalty ? item.penalty_amount! : item.financial_impact)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Card Bottom: Metadata and Action Button */}
                <div className="pt-3 border-t border-[var(--card-border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 text-[var(--text-sub)]">
                      <Clock className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                      <span>
                        Срок: <strong className="text-[var(--text-main)]">{formatDate(item.due_date)}</strong>
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[var(--text-sub)]">
                      <User className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                      <span>
                        Ответственный:{' '}
                        <span className="font-semibold text-[var(--text-main)]">{item.responsible}</span>
                      </span>
                    </div>
                  </div>

                  {/* Quick Action Button */}
                  <button
                    type="button"
                    onClick={() => handleActionClick(item)}
                    className="min-h-[40px] px-3.5 py-2 rounded-xl bg-white/80 dark:bg-zinc-900/80 hover:bg-white dark:hover:bg-zinc-800 border border-slate-200/80 dark:border-zinc-700/80 text-[var(--text-main)] font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer shrink-0 shadow-2xs"
                    id={`fire-detail-item-btn-${item.id}`}
                  >
                    <span>Перейти к объекту</span>
                    <ArrowUpRight className="h-3.5 w-3.5 text-[var(--text-sub)]" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
