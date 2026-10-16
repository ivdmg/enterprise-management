import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import type { DispatchRecordData, DispatchStatus } from '@/types';
import { LogIncidentModal } from './LogIncidentModal';
import {
  Radio,
  Truck,
  Users,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  Search,
  Building2,
  RefreshCw,
} from 'lucide-react';

interface StatusConfig {
  id: DispatchStatus;
  label: string;
  badgeClass: string;
  activeBtnClass: string;
  dotColor: string;
}

const STATUS_CONFIGS: Record<DispatchStatus, StatusConfig> = {
  on_site: {
    id: 'on_site',
    label: 'На объекте',
    badgeClass:
      'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/50',
    activeBtnClass: 'bg-emerald-600 text-white font-semibold shadow-sm',
    dotColor: 'bg-emerald-500',
  },
  repair: {
    id: 'repair',
    label: 'В ремонте',
    badgeClass:
      'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-900/50',
    activeBtnClass: 'bg-rose-600 text-white font-semibold shadow-sm',
    dotColor: 'bg-rose-500',
  },
  downtime: {
    id: 'downtime',
    label: 'Простой',
    badgeClass:
      'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-900/50',
    activeBtnClass: 'bg-amber-600 text-white font-semibold shadow-sm',
    dotColor: 'bg-amber-500',
  },
};

export function DispatchTab() {
  const [records, setRecords] = useState<DispatchRecordData[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [selectedIncidentRecord, setSelectedIncidentRecord] = useState<DispatchRecordData | null>(null);
  const [isIncidentModalOpen, setIsIncidentModalOpen] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadRecords = () => {
    setLoading(true);
    apiClient
      .getDispatchRecords()
      .then(setRecords)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRecords();
  }, []);

  const handleQuickStatusChange = async (recordId: string, newStatus: DispatchStatus) => {
    // If user clicked repair or downtime from 'on_site', suggest opening modal for details
    const targetRecord = records.find((r) => r.id === recordId);
    if (newStatus !== 'on_site' && targetRecord && targetRecord.status === 'on_site') {
      setSelectedIncidentRecord(targetRecord);
      setIsIncidentModalOpen(true);
      return;
    }

    setUpdatingId(recordId);
    // Optimistic update
    setRecords((prev) =>
      prev.map((r) =>
        r.id === recordId
          ? {
              ...r,
              status: newStatus,
              downtime_hours: newStatus === 'on_site' ? undefined : r.downtime_hours,
              downtime_reason: newStatus === 'on_site' ? undefined : r.downtime_reason,
            }
          : r
      )
    );

    try {
      await apiClient.updateDispatchStatus(recordId, newStatus);
    } catch (err) {
      console.error('Failed to update dispatch status:', err);
      loadRecords();
    } finally {
      setUpdatingId(null);
    }
  };

  const handleIncidentSubmit = async (
    recordId: string,
    payload: {
      status: DispatchStatus;
      downtime_reason: string;
      downtime_hours: number;
      incident_notes?: string;
    }
  ) => {
    setUpdatingId(recordId);
    try {
      const updated = await apiClient.logDispatchIncident(recordId, payload);
      setRecords((prev) => prev.map((r) => (r.id === recordId ? updated : r)));
    } catch (err) {
      console.error('Failed to log incident:', err);
      loadRecords();
    } finally {
      setUpdatingId(null);
    }
  };

  const openIncidentModal = (record: DispatchRecordData) => {
    setSelectedIncidentRecord(record);
    setIsIncidentModalOpen(true);
  };

  // Distinct objects
  const uniqueObjects = Array.from(new Set(records.map((r) => r.target_object)));

  // Filtering
  const filteredRecords = records.filter((rec) => {
    if (typeFilter !== 'all' && rec.resource_type !== typeFilter) return false;
    if (statusFilter !== 'all' && rec.status !== statusFilter) return false;
    if (projectFilter !== 'all' && rec.target_object !== projectFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = rec.unit_name.toLowerCase().includes(q);
      const matchResp = rec.responsible_person.toLowerCase().includes(q);
      const matchObj = rec.target_object.toLowerCase().includes(q);
      const matchReason = rec.downtime_reason?.toLowerCase().includes(q);
      if (!matchName && !matchResp && !matchObj && !matchReason) return false;
    }
    return true;
  });

  // KPI Calculations
  const totalCount = records.length;
  const onSiteCount = records.filter((r) => r.status === 'on_site').length;
  const repairCount = records.filter((r) => r.status === 'repair').length;
  const downtimeCount = records.filter((r) => r.status === 'downtime').length;
  const totalDowntimeHours = records.reduce((acc, r) => acc + (r.downtime_hours || 0), 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Radio className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Диспетчерская служба и суточный график
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Мобильный чеклист техники и строительных бригад, оперативная фиксация поломок и простоев
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="neutral">Смена: 16.10.2026</Badge>
          <button
            type="button"
            onClick={loadRecords}
            title="Обновить суточный статус"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Total units on shift */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">Всего ресурсов</span>
            <Truck className="h-4 w-4 text-slate-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {totalCount}
            </span>
            <span className="text-xs text-slate-500">ед. на смене</span>
          </div>
          <p className="text-[11px] text-slate-500">Техника + бригады</p>
        </div>

        {/* On site (active work) */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">В работе на объектах</span>
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {onSiteCount}
            </span>
            <span className="text-xs text-emerald-600 font-medium">
              {Math.round((onSiteCount / (totalCount || 1)) * 100)}% готовности
            </span>
          </div>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400">Штатный режим смены</p>
        </div>

        {/* In Repair */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">В ремонте</span>
            <div className="w-2 h-2 rounded-full bg-rose-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-rose-600 dark:text-rose-400">
              {repairCount}
            </span>
            <span className="text-xs text-rose-600 flex items-center gap-1 font-semibold">
              <Wrench className="h-3.5 w-3.5" />
              ТО / Поломка
            </span>
          </div>
          <p className="text-[11px] text-rose-600 dark:text-rose-400">Требуется вмешательство механиков</p>
        </div>

        {/* Downtime */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">Простой</span>
            <div className="w-2 h-2 rounded-full bg-amber-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
              {downtimeCount}
            </span>
            <span className="text-xs text-amber-600 font-mono font-medium">
              {totalDowntimeHours} ч. потерь
            </span>
          </div>
          <p className="text-[11px] text-amber-600 dark:text-amber-400">Ожидание самосвалов / погода</p>
        </div>
      </div>

      {/* Filters Bar */}
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
                placeholder="Поиск по технике, бригаде, ответственному или объекту..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400"
              />
            </div>

            {/* Object Filter Dropdown */}
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-slate-400 shrink-0" />
              <select
                value={projectFilter}
                onChange={(e) => setProjectFilter(e.target.value)}
                aria-label="Фильтр по объекту"
                className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="all">Все строительные площадки</option>
                {uniqueObjects.map((obj) => (
                  <option key={obj} value={obj}>
                    {obj}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Type and Status Filter Pills */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-100 dark:border-slate-800/80">
            {/* Resource Type */}
            <div className="flex items-center gap-1.5 overflow-x-auto">
              <span className="text-[11px] uppercase font-semibold text-slate-400 whitespace-nowrap mr-1">
                Тип:
              </span>
              {[
                { id: 'all', label: 'Все ресурсы' },
                { id: 'machinery', label: 'Спецтехника', icon: Truck },
                { id: 'crew', label: 'Бригады', icon: Users },
              ].map((tf) => (
                <button
                  key={tf.id}
                  onClick={() => setTypeFilter(tf.id)}
                  className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap flex items-center gap-1 ${
                    typeFilter === tf.id
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {tf.icon && <tf.icon className="h-3 w-3" />}
                  <span>{tf.label}</span>
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 overflow-x-auto">
              <span className="text-[11px] uppercase font-semibold text-slate-400 whitespace-nowrap mr-1">
                Статус:
              </span>
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap ${
                  statusFilter === 'all'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                Все ({records.length})
              </button>
              {(Object.keys(STATUS_CONFIGS) as DispatchStatus[]).map((st) => {
                const cfg = STATUS_CONFIGS[st];
                const count = records.filter((r) => r.status === st).length;
                return (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap flex items-center gap-1.5 ${
                      statusFilter === st
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${cfg.dotColor}`} />
                    <span>{cfg.label}</span>
                    <span className="text-[10px] opacity-75">({count})</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Card>

      {/* Main Checklist / Table */}
      <Card padding="none">
        {/* Desktop Table View (>= 768px) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm" id="dispatch-table">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Единица ресурса
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Объект смены
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Ответственный
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-72">
                  Статус (переключение в 1 клик)
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Инцидент / Заметки диспетчера
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-36">
                  Действие
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {filteredRecords.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-400 text-sm">
                    Единиц техники или бригад по выбранным фильтрам не найдено
                  </td>
                </tr>
              ) : (
                filteredRecords.map((rec) => {
                  const isMachinery = rec.resource_type === 'machinery';

                  return (
                    <tr
                      key={rec.id}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Unit name and type icon */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="flex items-start gap-2.5">
                          <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 mt-0.5">
                            {isMachinery ? (
                              <Truck className="h-4 w-4" />
                            ) : (
                              <Users className="h-4 w-4" />
                            )}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                              {rec.unit_name}
                            </p>
                            <p className="text-[11px] text-slate-500">
                              {isMachinery ? 'Спецтехника' : 'Строительная бригада'}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Object */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="flex items-center gap-1.5 text-slate-800 dark:text-slate-200">
                          <Building2 className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          <span className="text-xs font-medium">{rec.target_object}</span>
                        </div>
                      </td>

                      {/* Responsible person */}
                      <td className="px-4 py-3.5 align-top text-xs text-slate-700 dark:text-slate-300">
                        {rec.responsible_person}
                      </td>

                      {/* 1-Click Status Switcher Pills */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="inline-flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200/80 dark:border-slate-700">
                          {(Object.keys(STATUS_CONFIGS) as DispatchStatus[]).map((st) => {
                            const cfg = STATUS_CONFIGS[st];
                            const isActive = rec.status === st;

                            return (
                              <button
                                key={st}
                                type="button"
                                onClick={() => handleQuickStatusChange(rec.id, st)}
                                disabled={updatingId === rec.id}
                                className={`px-2.5 py-1 text-xs rounded-md transition-all flex items-center gap-1 cursor-pointer select-none ${
                                  isActive
                                    ? cfg.activeBtnClass
                                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                                }`}
                              >
                                <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotColor}`} />
                                <span>{cfg.label}</span>
                              </button>
                            );
                          })}
                        </div>
                      </td>

                      {/* Incident & Notes */}
                      <td className="px-4 py-3.5 align-top text-xs">
                        {rec.status === 'on_site' ? (
                          <span className="text-slate-400 flex items-center gap-1 text-[11px]">
                            <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                            Работает по суточному заданию
                          </span>
                        ) : (
                          <div className="space-y-1">
                            {rec.downtime_reason && (
                              <p className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                                <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                                {rec.downtime_reason}
                              </p>
                            )}
                            <div className="flex items-center gap-2 text-[11px] text-slate-500">
                              {rec.downtime_hours !== undefined && (
                                <span className="font-mono font-medium text-rose-600 dark:text-rose-400">
                                  Простой: {rec.downtime_hours} ч.
                                </span>
                              )}
                              {rec.incident_notes && (
                                <span className="truncate max-w-xs opacity-80">
                                  {rec.incident_notes}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </td>

                      {/* Action: Log / Edit incident */}
                      <td className="px-4 py-3.5 align-top text-right">
                        <button
                          type="button"
                          onClick={() => openIncidentModal(rec)}
                          className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm"
                        >
                          {rec.status === 'on_site' ? 'Поломка' : 'Изменить'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Checklist Cards View (< 768px) */}
        <div className="md:hidden divide-y divide-slate-200 dark:divide-slate-800" id="dispatch-mobile-cards">
          {filteredRecords.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              Единиц техники или бригад по выбранным фильтрам не найдено
            </div>
          ) : (
            filteredRecords.map((rec) => {
              const isMachinery = rec.resource_type === 'machinery';
              const statusCfg = STATUS_CONFIGS[rec.status];

              return (
                <div key={rec.id} className="p-4 space-y-3">
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2.5">
                      <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 mt-0.5">
                        {isMachinery ? <Truck className="h-4 w-4" /> : <Users className="h-4 w-4" />}
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                          {rec.unit_name}
                        </h4>
                        <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-0.5">
                          <Building2 className="h-3 w-3 text-slate-400" />
                          {rec.target_object}
                        </p>
                      </div>
                    </div>

                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold border flex items-center gap-1 ${statusCfg.badgeClass}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dotColor}`} />
                      {statusCfg.label}
                    </span>
                  </div>

                  {/* Responsible Person */}
                  <div className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-2 rounded-lg border border-slate-100 dark:border-slate-800/80">
                    <span className="text-[10px] uppercase font-semibold text-slate-400 block">Ответственный на смене:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{rec.responsible_person}</span>
                  </div>

                  {/* 1-Click Status Switcher (Mobile Large Targets >= 44px) */}
                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-semibold text-slate-400 block">
                      Сменить статус в 1 клик:
                    </span>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(Object.keys(STATUS_CONFIGS) as DispatchStatus[]).map((st) => {
                        const cfg = STATUS_CONFIGS[st];
                        const isActive = rec.status === st;

                        return (
                          <button
                            key={st}
                            type="button"
                            onClick={() => handleQuickStatusChange(rec.id, st)}
                            disabled={updatingId === rec.id}
                            className={`min-h-[44px] px-2 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all select-none border ${
                              isActive
                                ? `${cfg.activeBtnClass} border-transparent`
                                : 'bg-slate-100 dark:bg-slate-800 border-slate-200/80 dark:border-slate-700 text-slate-600 dark:text-slate-400'
                            }`}
                          >
                            <span className={`w-2 h-2 rounded-full ${cfg.dotColor}`} />
                            <span>{cfg.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Incident Alert Details (if repair or downtime) */}
                  {rec.status !== 'on_site' && (
                    <div className="bg-rose-50/70 dark:bg-rose-950/30 p-2.5 rounded-lg border border-rose-200/80 dark:border-rose-900/40 text-xs space-y-1">
                      <div className="flex items-center justify-between text-rose-800 dark:text-rose-300 font-semibold">
                        <span className="flex items-center gap-1">
                          <AlertTriangle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
                          {rec.status === 'repair' ? 'Аварийный ремонт' : 'Технический простой'}
                        </span>
                        {rec.downtime_hours !== undefined && (
                          <span className="font-mono">{rec.downtime_hours} ч.</span>
                        )}
                      </div>
                      {rec.downtime_reason && (
                        <p className="text-[11px] text-slate-700 dark:text-slate-300">
                          {rec.downtime_reason}
                        </p>
                      )}
                      {rec.incident_notes && (
                        <p className="text-[10px] text-slate-500 italic">
                          Меры: {rec.incident_notes}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Button: Зафиксировать поломку / простой */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => openIncidentModal(rec)}
                      className="w-full min-h-[44px] px-3 py-2 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm flex items-center justify-center gap-1.5"
                    >
                      <Wrench className="h-4 w-4 text-slate-500" />
                      <span>Зафиксировать поломку / простой</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* Incident Logging Modal */}
      <LogIncidentModal
        isOpen={isIncidentModalOpen}
        onClose={() => setIsIncidentModalOpen(false)}
        record={selectedIncidentRecord}
        onSubmit={handleIncidentSubmit}
      />
    </div>
  );
}
