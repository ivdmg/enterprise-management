import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { apiClient } from '@/api/client';
import { formatCurrency, formatDate } from '@/utils/format';
import type { ProcurementItemData, ProcurementStatus } from '@/types';
import {
  ShoppingBag,
  Truck,
  CheckCircle2,
  Clock,
  CreditCard,
  Search,
  Building2,
  ChevronDown,
  ArrowRight,
  PackageCheck,
  Calendar,
} from 'lucide-react';

interface StatusConfig {
  id: ProcurementStatus;
  label: string;
  badgeClass: string;
  dotColor: string;
  icon: typeof ShoppingBag;
  nextStatus?: ProcurementStatus;
  nextLabel?: string;
}

const STATUS_CONFIGS: Record<ProcurementStatus, StatusConfig> = {
  invoice_pending: {
    id: 'invoice_pending',
    label: 'Счет на оплате',
    badgeClass:
      'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border-blue-200 dark:border-blue-900/50',
    dotColor: 'bg-blue-500',
    icon: Clock,
    nextStatus: 'paid',
    nextLabel: 'Отметить оплаченным',
  },
  paid: {
    id: 'paid',
    label: 'Оплачено',
    badgeClass:
      'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-900/50',
    dotColor: 'bg-amber-500',
    icon: CreditCard,
    nextStatus: 'in_transit',
    nextLabel: 'Отгружено (в пути)',
  },
  in_transit: {
    id: 'in_transit',
    label: 'В пути',
    badgeClass:
      'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900/50',
    dotColor: 'bg-indigo-500',
    icon: Truck,
    nextStatus: 'delivered',
    nextLabel: 'Принять на объекте',
  },
  delivered: {
    id: 'delivered',
    label: 'На объекте',
    badgeClass:
      'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/50',
    dotColor: 'bg-emerald-500',
    icon: CheckCircle2,
  },
};

export function ProcurementTab() {
  const [items, setItems] = useState<ProcurementItemData[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadItems = () => {
    setLoading(true);
    apiClient
      .getProcurementItems()
      .then(setItems)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadItems();
  }, []);

  const handleStatusUpdate = async (itemId: string, newStatus: ProcurementStatus) => {
    setUpdatingId(itemId);
    setActiveDropdownId(null);

    // Optimistic update
    setItems((prev) =>
      prev.map((item) => (item.id === itemId ? { ...item, status: newStatus } : item))
    );

    try {
      await apiClient.updateProcurementStatus(itemId, newStatus);
    } catch (err) {
      console.error('Failed to update procurement status:', err);
      loadItems();
    } finally {
      setUpdatingId(null);
    }
  };

  // Distinct projects for filter
  const uniqueProjects = Array.from(new Set(items.map((i) => i.project_name)));

  // Filtering
  const filteredItems = items.filter((item) => {
    if (statusFilter !== 'all' && item.status !== statusFilter) return false;
    if (projectFilter !== 'all' && item.project_name !== projectFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = item.item_name.toLowerCase().includes(q);
      const matchSupplier = item.supplier.toLowerCase().includes(q);
      const matchProject = item.project_name.toLowerCase().includes(q);
      const matchInvoice = item.invoice_number?.toLowerCase().includes(q);
      if (!matchName && !matchSupplier && !matchProject && !matchInvoice) return false;
    }
    return true;
  });

  // KPI Calculations
  const totalSum = items.reduce((acc, i) => acc + i.invoice_amount, 0);
  const pendingCount = items.filter((i) => i.status === 'invoice_pending').length;
  const pendingSum = items
    .filter((i) => i.status === 'invoice_pending')
    .reduce((acc, i) => acc + i.invoice_amount, 0);

  const paidCount = items.filter((i) => i.status === 'paid').length;
  const paidSum = items
    .filter((i) => i.status === 'paid')
    .reduce((acc, i) => acc + i.invoice_amount, 0);

  const transitCount = items.filter((i) => i.status === 'in_transit').length;
  const deliveredCount = items.filter((i) => i.status === 'delivered').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Снабжение и закупки ТМЦ
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Реестр материалов по счетам, контроль логистики поставок и подтверждение приемки на объектах
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="neutral">Снабжение СМР</Badge>
          <div className="text-xs text-slate-500 dark:text-slate-400">
            Всего счетов на: <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">{formatCurrency(totalSum)}</span>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Pending Invoices */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">На оплате</span>
            <div className="w-2 h-2 rounded-full bg-blue-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {pendingCount}
            </span>
            <span className="text-xs text-slate-500 font-mono">{formatCurrency(pendingSum)}</span>
          </div>
          <p className="text-[11px] text-blue-600 dark:text-blue-400">Требуют согласования бухгалтерии</p>
        </div>

        {/* Paid & Packing */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">Оплачено</span>
            <div className="w-2 h-2 rounded-full bg-amber-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {paidCount}
            </span>
            <span className="text-xs text-slate-500 font-mono">{formatCurrency(paidSum)}</span>
          </div>
          <p className="text-[11px] text-amber-600 dark:text-amber-400">Комплектуются поставщиками</p>
        </div>

        {/* In Transit */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">В пути</span>
            <div className="w-2 h-2 rounded-full bg-indigo-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {transitCount}
            </span>
            <span className="text-xs text-indigo-600 dark:text-indigo-400 flex items-center gap-1 font-medium">
              <Truck className="h-3.5 w-3.5" />
              Доставка
            </span>
          </div>
          <p className="text-[11px] text-slate-500">Ожидаются на площадках</p>
        </div>

        {/* Delivered on Site */}
        <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase font-semibold text-slate-400">На объекте</span>
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
              {deliveredCount}
            </span>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
              <PackageCheck className="h-3.5 w-3.5" />
              Принято
            </span>
          </div>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400">Входной контроль пройден</p>
        </div>
      </div>

      {/* Filters and Search Bar */}
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
                placeholder="Поиск по ТМЦ, поставщику, объекту или номеру счета..."
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
                <option value="all">Все объекты строительства</option>
                {uniqueProjects.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Status Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-slate-100 dark:border-slate-800/80">
            <span className="text-[11px] uppercase font-semibold text-slate-400 whitespace-nowrap mr-1">
              Статус:
            </span>
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap ${
                statusFilter === 'all'
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              Все позиции ({items.length})
            </button>
            {(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => {
              const cfg = STATUS_CONFIGS[st];
              const count = items.filter((i) => i.status === st).length;
              return (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors whitespace-nowrap flex items-center gap-1.5 ${
                    statusFilter === st
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
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
      </Card>

      {/* Main Registry */}
      <Card padding="none">
        {/* Desktop Table View (>= 768px) */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm" id="procurement-table">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Номенклатура ТМЦ
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Объект СМР
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Поставщик и счет
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Объем
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Сумма счета
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Срок поставки
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider w-48">
                  Статус и действие
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400 text-sm">
                    Позиций ТМЦ по выбранным фильтрам не найдено
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const statusCfg = STATUS_CONFIGS[item.status];
                  const isMenuOpen = activeDropdownId === item.id;

                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      {/* Item Name */}
                      <td className="px-4 py-3.5 align-top">
                        <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                          {item.item_name}
                        </p>
                      </td>

                      {/* Project */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                          <Building2 className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          <span className="text-xs font-medium">{item.project_name}</span>
                        </div>
                      </td>

                      {/* Supplier & Invoice */}
                      <td className="px-4 py-3.5 align-top">
                        <p className="text-xs font-medium text-slate-900 dark:text-slate-100">
                          {item.supplier}
                        </p>
                        {item.invoice_number && (
                          <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                            {item.invoice_number}
                          </p>
                        )}
                      </td>

                      {/* Quantity */}
                      <td className="px-4 py-3.5 text-right font-mono text-xs text-slate-800 dark:text-slate-200 align-top">
                        <span className="font-semibold">{item.quantity}</span>{' '}
                        <span className="text-slate-500">{item.unit}</span>
                      </td>

                      {/* Amount */}
                      <td className="px-4 py-3.5 text-right font-mono font-semibold text-slate-900 dark:text-slate-100 align-top">
                        {formatCurrency(item.invoice_amount)}
                      </td>

                      {/* Delivery Deadline */}
                      <td className="px-4 py-3.5 align-top text-xs">
                        <div className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                          <Calendar className="h-3 w-3 text-slate-400" />
                          <span>{formatDate(item.delivery_deadline)}</span>
                        </div>
                      </td>

                      {/* Status Dropdown / Action */}
                      <td className="px-4 py-3.5 align-top text-center">
                        <div className="relative inline-block text-left">
                          <button
                            type="button"
                            onClick={() =>
                              setActiveDropdownId(isMenuOpen ? null : item.id)
                            }
                            disabled={updatingId === item.id}
                            className={`px-2.5 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm ${statusCfg.badgeClass}`}
                          >
                            <span className={`w-2 h-2 rounded-full ${statusCfg.dotColor}`} />
                            <span>{statusCfg.label}</span>
                            <ChevronDown className="h-3 w-3 opacity-60 ml-0.5" />
                          </button>

                          {/* Quick Dropdown Menu */}
                          {isMenuOpen && (
                            <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-1.5 z-30">
                              <div className="px-3 py-1 text-[10px] uppercase font-bold text-slate-400 border-b border-slate-100 dark:border-slate-800">
                                Сменить статус:
                              </div>
                              {(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => {
                                const opt = STATUS_CONFIGS[st];
                                return (
                                  <button
                                    key={st}
                                    type="button"
                                    onClick={() => handleStatusUpdate(item.id, st)}
                                    className={`w-full px-3 py-2 text-xs text-left flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                                      item.status === st
                                        ? 'font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/20'
                                        : 'text-slate-700 dark:text-slate-300'
                                    }`}
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className={`w-2 h-2 rounded-full ${opt.dotColor}`} />
                                      <span>{opt.label}</span>
                                    </div>
                                    {item.status === st && (
                                      <CheckCircle2 className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards View (< 768px) */}
        <div className="md:hidden divide-y divide-slate-200 dark:divide-slate-800" id="procurement-mobile-cards">
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              Позиций ТМЦ по выбранным фильтрам не найдено
            </div>
          ) : (
            filteredItems.map((item) => {
              const statusCfg = STATUS_CONFIGS[item.status];
              const isMenuOpen = activeDropdownId === item.id;

              return (
                <div key={item.id} className="p-4 space-y-3">
                  {/* Item header & status */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5">
                      <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                        {item.item_name}
                      </h4>
                      <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                        <Building2 className="h-3 w-3 text-slate-400" />
                        {item.project_name}
                      </p>
                    </div>

                    {/* Status badge button */}
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setActiveDropdownId(isMenuOpen ? null : item.id)}
                        className={`px-2.5 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 shadow-sm min-h-[36px] ${statusCfg.badgeClass}`}
                      >
                        <span className={`w-2 h-2 rounded-full ${statusCfg.dotColor}`} />
                        <span>{statusCfg.label}</span>
                        <ChevronDown className="h-3 w-3 opacity-60 ml-0.5" />
                      </button>

                      {isMenuOpen && (
                        <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-1.5 z-30">
                          <div className="px-3 py-1 text-[10px] uppercase font-bold text-slate-400 border-b border-slate-100 dark:border-slate-800">
                            Сменить статус:
                          </div>
                          {(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => {
                            const opt = STATUS_CONFIGS[st];
                            return (
                              <button
                                key={st}
                                type="button"
                                onClick={() => handleStatusUpdate(item.id, st)}
                                className={`w-full px-3 py-2 text-xs text-left flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                                  item.status === st
                                    ? 'font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/20'
                                    : 'text-slate-700 dark:text-slate-300'
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  <span className={`w-2 h-2 rounded-full ${opt.dotColor}`} />
                                  <span>{opt.label}</span>
                                </div>
                                {item.status === st && (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Volume, Supplier, and Amount Grid */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] uppercase font-medium text-slate-400">Сумма и объем</span>
                      <p className="text-sm font-semibold font-mono text-slate-900 dark:text-slate-100 mt-0.5">
                        {formatCurrency(item.invoice_amount)}
                      </p>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">
                        {item.quantity} {item.unit}
                      </p>
                    </div>

                    <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] uppercase font-medium text-slate-400">Поставщик</span>
                      <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 mt-0.5 truncate">
                        {item.supplier}
                      </p>
                      <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                        {item.invoice_number || 'Счет согласован'}
                      </p>
                    </div>
                  </div>

                  {/* Delivery date & Next Stage Action Button */}
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Calendar className="h-3.5 w-3.5 text-slate-400" />
                      <span>Поставка до {formatDate(item.delivery_deadline)}</span>
                    </div>

                    {statusCfg.nextStatus && (
                      <button
                        type="button"
                        onClick={() => handleStatusUpdate(item.id, statusCfg.nextStatus!)}
                        disabled={updatingId === item.id}
                        className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 flex items-center gap-1 transition-colors min-h-[36px]"
                      >
                        <span>{statusCfg.nextLabel}</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>
    </div>
  );
}
