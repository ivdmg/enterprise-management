import { useState } from 'react';
import {
  Flame,
  AlertTriangle,
  ArrowUpRight,
  Clock,
  User,
  Building2,
  Scale,
  ShieldAlert,
  FileText,
  DollarSign,
} from 'lucide-react';
import { Badge } from '@/components/Badge';
import { formatDate, formatCurrency } from '@/utils/format';
import type { FireItem } from '@/types';

interface FirePanelProps {
  items: FireItem[];
  onNavigateToProject?: (projectId: string) => void;
  onNavigateTab?: (tabId: string) => void;
}

type FilterType = 'all' | 'critical' | 'warning' | 'penalties';

export function FirePanel({ items, onNavigateToProject, onNavigateTab }: FirePanelProps) {
  const [filter, setFilter] = useState<FilterType>('all');

  const criticalCount = items.filter((i) => i.severity === 'CRITICAL').length;
  const warningCount = items.filter((i) => i.severity === 'WARNING').length;
  const penaltiesCount = items.filter((i) => (i.penalty_amount || 0) > 0 || (i.days_overdue || 0) > 0).length;

  const filteredItems = items.filter((item) => {
    if (filter === 'critical') return item.severity === 'CRITICAL';
    if (filter === 'warning') return item.severity === 'WARNING';
    if (filter === 'penalties') return (item.penalty_amount || 0) > 0 || (item.days_overdue || 0) > 0;
    return true;
  });

  const handleActionClick = (item: FireItem) => {
    if (item.project_id && onNavigateToProject) {
      onNavigateToProject(item.project_id);
    } else if (onNavigateTab) {
      onNavigateTab('tenders');
    }
  };

  const getItemCategoryIcon = (category?: string, severity?: string) => {
    const iconClass = "h-4 w-4 shrink-0";
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

  return (
    <div className="space-y-4" id="fire-panel-section">
      {/* Header and Filter Pills */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <Flame className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-semibold text-slate-900 dark:text-slate-100">
                Экран «Где горит?»
              </h2>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-900/40">
                {items.length} активных риска
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              События с дедлайном &le; 5 дней, риски неустоек по 44-ФЗ и банковских гарантий
            </p>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none pb-1 sm:pb-0">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
              filter === 'all'
                ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            Все ({items.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter('critical')}
            className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
              filter === 'critical'
                ? 'bg-rose-600 text-white font-semibold'
                : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20'
            }`}
          >
            Критические ({criticalCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter('warning')}
            className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
              filter === 'warning'
                ? 'bg-amber-600 text-white font-semibold'
                : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/20'
            }`}
          >
            Внимание ({warningCount})
          </button>
          <button
            type="button"
            onClick={() => setFilter('penalties')}
            className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer ${
              filter === 'penalties'
                ? 'bg-indigo-600 text-white font-semibold'
                : 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50'
            }`}
          >
            Штрафы и просрочки ({penaltiesCount})
          </button>
        </div>
      </div>

      {/* Fire Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5" id="fire-cards-container">
        {filteredItems.map((item) => {
          const isCritical = item.severity === 'CRITICAL';
          const hasPenalty = (item.penalty_amount || 0) > 0;
          const isOverdue = (item.days_overdue || 0) > 0;

          return (
            <div
              key={item.id}
              className={`rounded-xl border p-4 sm:p-5 transition-all flex flex-col justify-between gap-4 ${
                isCritical
                  ? 'bg-white dark:bg-slate-900 border-rose-200 dark:border-rose-900/50 shadow-2xs'
                  : 'bg-white dark:bg-slate-900 border-amber-200 dark:border-amber-900/50 shadow-2xs'
              }`}
            >
              {/* Card Top: Severity Badge, Title, Category Icon */}
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={isCritical ? 'danger' : 'warning'}>
                      <span className="flex items-center gap-1">
                        {getItemCategoryIcon(item.category, item.severity)}
                        <span>{isCritical ? 'Критический риск' : 'Внимание'}</span>
                      </span>
                    </Badge>

                    {isOverdue && (
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-rose-100 text-rose-700 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-200 dark:border-rose-900/50">
                        Просрочка +{item.days_overdue} дн.
                      </span>
                    )}

                    {!isOverdue && item.days_remaining !== undefined && item.days_remaining > 0 && (
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-200 dark:border-amber-900/50">
                        Осталось {item.days_remaining} дн.
                      </span>
                    )}
                  </div>

                  {item.project_name && (
                    <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1 shrink-0">
                      <Building2 className="h-3 w-3" />
                      <span className="max-w-[140px] truncate">{item.project_name}</span>
                    </span>
                  )}
                </div>

                {/* Title and Description */}
                <div>
                  <h3 className="text-sm sm:text-base font-semibold text-slate-900 dark:text-slate-100 leading-snug">
                    {item.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
                    {item.description}
                  </p>
                </div>

                {/* Financial Impact / Penalty Box */}
                {(item.financial_impact > 0 || hasPenalty) && (
                  <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200/80 dark:border-slate-800 text-xs">
                    <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                      <FileText className="h-3.5 w-3.5 text-slate-400" />
                      <span>{hasPenalty ? 'Расчетный штраф (44-ФЗ):' : 'Финансовый объем риска:'}</span>
                    </div>
                    <span className="font-mono font-bold text-rose-600 dark:text-rose-400 text-sm">
                      {formatCurrency(hasPenalty ? item.penalty_amount! : item.financial_impact)}
                    </span>
                  </div>
                )}
              </div>

              {/* Card Bottom: Metadata and Action Button */}
              <div className="pt-3 border-t border-slate-100 dark:border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                    <Clock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span>Срок: <strong className="text-slate-900 dark:text-slate-200">{formatDate(item.due_date)}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                    <User className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                    <span>Ответственный: <span className="font-medium text-slate-800 dark:text-slate-300">{item.responsible}</span></span>
                  </div>
                </div>

                {/* Quick Action Button */}
                <button
                  type="button"
                  onClick={() => handleActionClick(item)}
                  className="min-h-[44px] px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-medium text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer shrink-0"
                  id={`fire-item-btn-${item.id}`}
                >
                  <span>Перейти к объекту</span>
                  <ArrowUpRight className="h-3.5 w-3.5 text-slate-500" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
