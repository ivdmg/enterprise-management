import { useEffect, useState } from 'react';
import { Wallet, AlertTriangle, Building2, Calculator } from 'lucide-react';
import { KpiCard } from '@/components/KpiCard';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatCurrencyShort, formatDate } from '@/utils/format';
import type { DashboardSummary } from '@/types';

export function DashboardTab() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getDashboardSummary()
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

  const { financial_health, production_health, alerts_overview, top_fire_items } = data;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="kpi-cards-row">
        <KpiCard
          title="Свободные ДС"
          value={formatCurrencyShort(financial_health.current_cash_balance)}
          icon={Wallet}
          subtitle={financial_health.is_cash_gap_predicted ? 'Прогноз: кассовый разрыв' : 'Кассовый разрыв не прогнозируется'}
          trend={
            financial_health.is_cash_gap_predicted
              ? { value: `Дефицит: ${formatCurrencyShort(financial_health.gap_deficit_amount || 0)}`, positive: false }
              : undefined
          }
        />
        <KpiCard
          title="Кассовый разрыв (14 дн.)"
          value={financial_health.is_cash_gap_predicted ? 'Да' : 'Нет'}
          icon={AlertTriangle}
          subtitle={
            financial_health.is_cash_gap_predicted && financial_health.gap_date
              ? `Дата: ${formatDate(financial_health.gap_date)}`
              : 'Прогноз стабильный'
          }
        />
        <KpiCard
          title="Активные объекты"
          value={String(production_health.total_active_projects)}
          icon={Building2}
          subtitle={`Под риском: ${production_health.projects_at_risk_count}`}
          trend={
            production_health.projects_at_risk_count > 0
              ? { value: `${production_health.projects_at_risk_count} проекта требуют внимания`, positive: false }
              : undefined
          }
        />
        <KpiCard
          title="Сумма расч. штрафов"
          value={formatCurrencyShort(production_health.total_calculated_penalties)}
          icon={Calculator}
          subtitle="По просроченным объектам"
        />
      </div>

      {/* Fire items */}
      <div>
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-3">
          Где горит?
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" id="fire-items-grid">
          {top_fire_items.map((item) => (
            <Card key={item.id} className="hover:border-slate-300 dark:hover:border-slate-700 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={item.severity === 'CRITICAL' ? 'danger' : 'warning'}>
                      {item.severity === 'CRITICAL' ? 'Критично' : 'Внимание'}
                    </Badge>
                  </div>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {item.title}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    {item.description}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-500 dark:text-slate-400">
                    <span>Срок: {formatDate(item.due_date)}</span>
                    <span>Ответственный: {item.responsible}</span>
                  </div>
                </div>
                {item.financial_impact > 0 && (
                  <div className="text-right shrink-0">
                    <p className="text-sm font-semibold text-rose-600 dark:text-rose-400">
                      {formatCurrency(item.financial_impact)}
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">ущерб</p>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Alerts summary */}
      <Card>
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
          Сводка по алертам
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-rose-500" />
            <span className="text-sm text-slate-700 dark:text-slate-300">
              Критические: <span className="font-semibold">{alerts_overview.critical_count}</span>
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            <span className="text-sm text-slate-700 dark:text-slate-300">
              Предупреждения: <span className="font-semibold">{alerts_overview.warning_count}</span>
            </span>
          </div>
          {alerts_overview.info_count !== undefined && (
            <div className="flex items-center gap-1.5">
              <div className="h-2.5 w-2.5 rounded-full bg-slate-400" />
              <span className="text-sm text-slate-700 dark:text-slate-300">
                Инфо: <span className="font-semibold">{alerts_overview.info_count}</span>
              </span>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
