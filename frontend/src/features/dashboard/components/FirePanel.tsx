import { useState } from 'react';
import {
  Flame,
  AlertTriangle,
  Scale,
  ChevronRight,
  ArrowUpRight,
  Layers,
} from 'lucide-react';
import { formatCurrency } from '@/utils/format';
import type { FireItem } from '@/types';
import { FireDetailView } from './FireDetailView';

interface FirePanelProps {
  items: FireItem[];
  onNavigateToProject?: (projectId: string) => void;
  onNavigateTab?: (tabId: string) => void;
}

export function FirePanel({ items, onNavigateToProject, onNavigateTab }: FirePanelProps) {
  // State for drill-down view: null when in Executive 3-card overview mode
  const [drillDownCategory, setDrillDownCategory] = useState<'all' | 'critical' | 'warning' | 'penalties' | null>(null);

  // Critical items & total financial sum
  const criticalItems = items.filter((i) => i.severity === 'CRITICAL');
  const criticalCount = criticalItems.length;
  const criticalFinancialSum = criticalItems.reduce((acc, i) => acc + (i.financial_impact || 0) + (i.penalty_amount || 0), 0);

  // Warning items & total financial sum
  const warningItems = items.filter((i) => i.severity === 'WARNING');
  const warningCount = warningItems.length;
  const warningFinancialSum = warningItems.reduce((acc, i) => acc + (i.financial_impact || 0), 0);

  // Penalties items & total penalty sum
  const penaltiesItems = items.filter((i) => (i.penalty_amount || 0) > 0 || (i.days_overdue || 0) > 0);
  const penaltiesCount = penaltiesItems.length;
  const totalPenaltiesSum = penaltiesItems.reduce((acc, i) => acc + (i.penalty_amount || 0), 0);

  // Total overall financial risk volume
  const totalRiskSum = items.reduce((acc, i) => acc + (i.financial_impact || 0) + (i.penalty_amount || 0), 0);

  // If user clicked any of the 3 cards or "View all", show the Drill-Down detailed screen
  if (drillDownCategory !== null) {
    return (
      <FireDetailView
        items={items}
        initialCategory={drillDownCategory}
        onBack={() => setDrillDownCategory(null)}
        onNavigateToProject={onNavigateToProject}
        onNavigateTab={onNavigateTab}
      />
    );
  }

  // ============================================================
  // EXECUTIVE SUMMARY: 3 COMPACT BENTO-BOX CARDS (FE-2.1)
  // ============================================================
  return (
    <section aria-labelledby="fire-panel-heading" className="space-y-3.5" id="fire-panel-section">
      {/* Header and Quick Switch to Full List */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300 border border-red-200 dark:border-red-900/40 shrink-0">
            <Flame className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 id="fire-panel-heading" className="text-base sm:text-lg font-bold text-[var(--text-main)]">
                Оперативный экран «Где горит?»
              </h2>
              <span className="shrink-0 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950/70 dark:text-red-200 border border-red-200 dark:border-red-800/60 whitespace-nowrap">
                {items.length} активных риска
              </span>
            </div>
            <p className="text-xs text-[var(--text-sub)]">
              События с дедлайном &le; 5 дней, риски неустоек по 44-ФЗ и банковских гарантий
            </p>
          </div>
        </div>

        {/* Action to view full list */}
        <button
          type="button"
          onClick={() => setDrillDownCategory('all')}
          className="min-h-[38px] px-3.5 py-1.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--card-subtle)] text-[var(--text-main)] text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer self-start sm:self-auto shadow-2xs"
          id="fire-view-all-btn"
        >
          <Layers className="h-3.5 w-3.5 text-[var(--text-sub)]" />
          <span>Все риски ({items.length})</span>
          <ChevronRight className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        </button>
      </div>

      {/* 3 Executive Key Bento Cards (FE-2.2: Solid Corporate Palette) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 sm:gap-4" id="fire-cards-trio-row">
        {/* 1. КРИТИЧЕСКИЕ РИСКИ */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => setDrillDownCategory('critical')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setDrillDownCategory('critical');
            }
          }}
          className="rounded-2xl border p-5 transition-all flex flex-col justify-between gap-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] cursor-pointer select-none bg-red-50/90 border-red-300 hover:bg-red-100/80 hover:-translate-y-0.5 hover:shadow-md dark:bg-red-950/60 dark:border-red-800 dark:hover:bg-red-950/80"
          id="fire-card-critical"
        >
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="p-2 rounded-xl bg-red-100 dark:bg-red-900/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800">
                <Flame className="h-5 w-5" />
              </div>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200 border border-red-300 dark:border-red-800">
                Дедлайн &le; 3 дн.
              </span>
            </div>

            <div>
              <div className="text-3xl font-bold font-mono text-red-700 dark:text-red-300 tracking-tight">
                {criticalCount}
              </div>
              <h3 className="text-sm font-bold text-[var(--text-main)] mt-1">
                Критические риски
              </h3>
              <p className="text-xs text-[var(--text-sub)] mt-0.5 line-clamp-2">
                Срыв подписания КС-2, угроза расторжения по 44-ФЗ и блокировки гарантий
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-red-200 dark:border-red-900/60 flex items-center justify-between text-xs">
            <div className="flex flex-col">
              <span className="text-[10px] text-[var(--text-sub)] uppercase tracking-wider font-medium">
                Объем риска:
              </span>
              <span className="font-mono font-bold text-[var(--text-main)]">
                {formatCurrency(criticalFinancialSum)}
              </span>
            </div>
            <span className="text-xs font-semibold text-red-700 dark:text-red-300 flex items-center gap-1">
              <span>Открыть</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>

        {/* 2. ВНИМАНИЕ И ПРЕДУПРЕЖДЕНИЯ */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => setDrillDownCategory('warning')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setDrillDownCategory('warning');
            }
          }}
          className="rounded-2xl border p-5 transition-all flex flex-col justify-between gap-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] cursor-pointer select-none bg-amber-50/90 border-amber-300 hover:bg-amber-100/80 hover:-translate-y-0.5 hover:shadow-md dark:bg-amber-950/60 dark:border-amber-800 dark:hover:bg-amber-950/80"
          id="fire-card-warning"
        >
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-200 border border-amber-300 dark:border-amber-800">
                Дедлайн 4-5 дн.
              </span>
            </div>

            <div>
              <div className="text-3xl font-bold font-mono text-amber-700 dark:text-amber-300 tracking-tight">
                {warningCount}
              </div>
              <h3 className="text-sm font-bold text-[var(--text-main)] mt-1">
                Внимание и предупреждения
              </h3>
              <p className="text-xs text-[var(--text-sub)] mt-0.5 line-clamp-2">
                Протоколы разногласий, задержки материалов и согласование доп. соглашений
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-amber-200 dark:border-amber-900/60 flex items-center justify-between text-xs">
            <div className="flex flex-col">
              <span className="text-[10px] text-[var(--text-sub)] uppercase tracking-wider font-medium">
                Объем риска:
              </span>
              <span className="font-mono font-bold text-[var(--text-main)]">
                {formatCurrency(warningFinancialSum)}
              </span>
            </div>
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1">
              <span>Открыть</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>

        {/* 3. ШТРАФЫ И ПРОСРОЧКИ */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => setDrillDownCategory('penalties')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setDrillDownCategory('penalties');
            }
          }}
          className="rounded-2xl border p-5 transition-all flex flex-col justify-between gap-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] cursor-pointer select-none bg-[var(--card-subtle)] border-[var(--card-border)] hover:bg-[var(--card-bg)] hover:-translate-y-0.5 hover:shadow-md hover:border-[var(--card-subtle-border)]"
          id="fire-card-penalties"
        >
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="p-2 rounded-xl bg-slate-900/10 dark:bg-white/10 text-[var(--text-main)] border border-[var(--card-border)]">
                <Scale className="h-5 w-5" />
              </div>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-[var(--card-bg)] text-[var(--text-main)] border border-[var(--card-border)]">
                Расчет 44-ФЗ
              </span>
            </div>

            <div>
              <div className="text-3xl font-bold font-mono text-[var(--text-main)] tracking-tight">
                {penaltiesCount}
              </div>
              <h3 className="text-sm font-bold text-[var(--text-main)] mt-1">
                Штрафы и просрочки
              </h3>
              <p className="text-xs text-[var(--text-sub)] mt-0.5 line-clamp-2">
                Начисленные пени заказчиками и просрочки исполнения этапов договоров
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-[var(--card-border)] flex items-center justify-between text-xs">
            <div className="flex flex-col">
              <span className="text-[10px] text-[var(--text-sub)] uppercase tracking-wider font-medium">
                Расчетная сумма:
              </span>
              <span className="font-mono font-bold text-red-700 dark:text-red-300">
                {formatCurrency(totalPenaltiesSum)}
              </span>
            </div>
            <span className="text-xs font-semibold text-[var(--text-main)] flex items-center gap-1">
              <span>Открыть</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
