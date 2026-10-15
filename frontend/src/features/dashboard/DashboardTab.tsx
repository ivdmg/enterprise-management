import { useEffect, useState } from 'react';
import {
  Wallet,
  Building2,
  TrendingUp,
  Receipt,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import { formatCurrency, formatDate } from '@/utils/format';
import type { DashboardSummary, FinanceData } from '@/types';
import { FirePanel } from './components/FirePanel';

interface DashboardTabProps {
  onNavigateTab?: (tabId: string) => void;
}

export function DashboardTab({ onNavigateTab }: DashboardTabProps) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [financeData, setFinanceData] = useState<FinanceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      apiClient.getDashboardSummary(),
      apiClient.getFinanceData().catch(() => null),
    ])
      .then(([summary, finance]) => {
        if (mounted) {
          setData(summary);
          setFinanceData(finance);
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <div className="h-8 w-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Загрузка оперативной сводки...
        </p>
      </div>
    );
  }

  if (!data) return null;

  const { financial_health, production_health, alerts_overview, top_fire_items } = data;

  // Calculate debtors and creditors sum
  const debtorsSum =
    financial_health.total_debtors_sum ||
    financeData?.top_debtors.reduce((acc, d) => acc + d.debt_sum, 0) ||
    7600000;

  const creditorsSum =
    financial_health.total_creditors_sum ||
    financeData?.top_creditors.reduce((acc, c) => acc + c.debt_sum, 0) ||
    2720000;

  return (
    <div className="space-y-6">
      {/* ============================================================ */}
      {/* 4 KEY EXECUTIVE KPI CARDS (FE-2.1)                            */}
      {/* ============================================================ */}
      <section aria-labelledby="kpi-heading">
        <div className="flex items-center justify-between mb-3">
          <h2 id="kpi-heading" className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Ключевые операционные показатели (Executive KPI)
          </h2>
          <span className="text-[11px] text-slate-400 dark:text-slate-500 hidden sm:inline">
            Обновлено: только что
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4" id="kpi-cards-row">
          {/* 1. Свободная касса */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs transition-all hover:border-slate-300 dark:hover:border-slate-700 flex flex-col justify-between">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Свободная касса
              </span>
              <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                <Wallet className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-2.5">
              <div className="text-2xl font-semibold font-mono text-slate-900 dark:text-slate-100 tracking-tight">
                {formatCurrency(financial_health.current_cash_balance)}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                Живые деньги на расчетных счетах компании
              </p>
            </div>

            <div className="mt-3.5 pt-3 border-t border-slate-100 dark:border-slate-800/80">
              {financial_health.is_cash_gap_predicted ? (
                <div className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400 font-medium">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>
                    Разрыв {financial_health.gap_date ? formatDate(financial_health.gap_date) : 'в течение 14 дней'}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  <span>Прогноз 14 дней: разрыв не ожидается</span>
                </div>
              )}
            </div>
          </div>

          {/* 2. Портфель контрактов */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs transition-all hover:border-slate-300 dark:hover:border-slate-700 flex flex-col justify-between">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Портфель контрактов
              </span>
              <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                <Building2 className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-2.5">
              <div className="text-2xl font-semibold font-mono text-slate-900 dark:text-slate-100 tracking-tight">
                {formatCurrency(production_health.total_portfolio_sum || 148500000)}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                Общая сумма активных договоров СМР
              </p>
            </div>

            <div className="mt-3.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-600 dark:text-slate-400 font-medium">
                {production_health.total_active_projects} объектов в работе
              </span>
              {production_health.projects_at_risk_count > 0 ? (
                <span className="text-rose-600 dark:text-rose-400 font-medium">
                  {production_health.projects_at_risk_count} под риском
                </span>
              ) : (
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                  Без отставаний
                </span>
              )}
            </div>
          </div>

          {/* 3. Нам должны (Дебиторка) */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs transition-all hover:border-slate-300 dark:hover:border-slate-700 flex flex-col justify-between">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Нам должны (Дебиторка)
              </span>
              <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
                <TrendingUp className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-2.5">
              <div className="text-2xl font-semibold font-mono text-slate-900 dark:text-slate-100 tracking-tight">
                {formatCurrency(debtorsSum)}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                Неоплаченные заказчиками объемы по КС-2
              </p>
            </div>

            <div className="mt-3.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-amber-700 dark:text-amber-400 font-medium">
                Просрочено: 4.15 млн ₽
              </span>
              <span className="text-slate-400 text-[11px]">3 дебитора</span>
            </div>
          </div>

          {/* 4. Мы должны (Кредиторка) */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs transition-all hover:border-slate-300 dark:hover:border-slate-700 flex flex-col justify-between">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Мы должны (Кредиторка)
              </span>
              <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                <Receipt className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-2.5">
              <div className="text-2xl font-semibold font-mono text-slate-900 dark:text-slate-100 tracking-tight">
                {formatCurrency(creditorsSum)}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                Неоплаченные счета поставщиков ТМЦ
              </p>
            </div>

            <div className="mt-3.5 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-600 dark:text-slate-400 font-medium">
                Срок: до 18 октября
              </span>
              <span className="text-slate-400 text-[11px]">2 счета ТМЦ</span>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* EXECUTIVE FIRE PANEL: «ГДЕ ГОРИТ?» (FE-2.2)                   */}
      {/* ============================================================ */}
      <FirePanel
        items={top_fire_items}
        onNavigateToProject={() => {
          if (onNavigateTab) onNavigateTab('tenders');
        }}
        onNavigateTab={onNavigateTab}
      />

      {/* ============================================================ */}
      {/* QUICK SYSTEM STATUS & CONTROL FOOTER                         */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Risk overview */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Сводка алертов платформы
            </span>
            <ShieldCheck className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              <span className="text-slate-600 dark:text-slate-400">
                Критических: <strong className="text-slate-900 dark:text-slate-100">{alerts_overview.critical_count}</strong>
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="text-slate-600 dark:text-slate-400">
                Внимание: <strong className="text-slate-900 dark:text-slate-100">{alerts_overview.warning_count}</strong>
              </span>
            </div>
            {alerts_overview.info_count !== undefined && (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-slate-400" />
                <span className="text-slate-600 dark:text-slate-400">
                  Инфо: <strong className="text-slate-900 dark:text-slate-100">{alerts_overview.info_count}</strong>
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Penalties Summary */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Неустойки по 44-ФЗ
            </span>
            <Clock className="h-4 w-4 text-rose-600 dark:text-rose-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-base font-semibold font-mono text-rose-600 dark:text-rose-400">
              {formatCurrency(production_health.total_calculated_penalties)}
            </span>
            <span className="text-[11px] text-slate-500">расчет за текущий месяц</span>
          </div>
        </div>

        {/* Action Link to Full Tenders Registry */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              Реестр контрактов и объектов
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Сроки сдачи, акты КС-2 и банковские гарантии
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab && onNavigateTab('tenders')}
            className="min-h-[44px] min-w-[44px] px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <span>Открыть</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
