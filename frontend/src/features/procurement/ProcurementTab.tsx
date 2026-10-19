import { useEffect, useState } from 'react';
import { Card } from '@/components/Card';
import { Badge } from '@/components/Badge';
import { Select } from '@/components/Select';
import { ConfirmModal } from '@/components/ConfirmModal';
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
  Calendar,
  ChevronUp,
  FileText,
  Package,
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
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    dotColor: 'bg-slate-500',
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
      'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border-blue-200 dark:border-blue-900/50',
    dotColor: 'bg-blue-500',
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

  // Mobile Accordion state: set of expanded item IDs (FE-4.2)
  const [expandedCardIds, setExpandedCardIds] = useState<Set<string>>(new Set());

  // ConfirmModal state for status changes (FE-4.3)
  const [pendingStatusChange, setPendingStatusChange] = useState<{
    item: ProcurementItemData;
    targetStatus: ProcurementStatus;
  } | null>(null);

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

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.procurement-status-dropdown-container')) {
        setActiveDropdownId(null);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  // Triggered when user selects new status in dropdown or clicks next action button
  const requestStatusChange = (item: ProcurementItemData, targetStatus: ProcurementStatus) => {
    if (item.status === targetStatus) {
      setActiveDropdownId(null);
      return;
    }
    setActiveDropdownId(null);
    setPendingStatusChange({ item, targetStatus });
  };

  // Confirmed in modal
  const handleConfirmStatusChange = async () => {
    if (!pendingStatusChange) return;
    const { item, targetStatus } = pendingStatusChange;
    const itemId = item.id;

    setUpdatingId(itemId);
    setPendingStatusChange(null);

    // Optimistic update
    setItems((prev) =>
      prev.map((i) => (i.id === itemId ? { ...i, status: targetStatus } : i))
    );

    try {
      await apiClient.updateProcurementStatus(itemId, targetStatus);
    } catch (err) {
      console.error('Failed to update procurement status:', err);
      loadItems();
    } finally {
      setUpdatingId(null);
    }
  };

  // Toggle mobile accordion card
  const toggleCardExpand = (id: string) => {
    setExpandedCardIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Distinct projects for custom Select filter (FE-4.1)
  const uniqueProjects = Array.from(new Set(items.map((i) => i.project_name)));
  const projectOptions = [
    { value: 'all', label: 'Все объекты строительства' },
    ...uniqueProjects.map((p) => ({ value: p, label: p })),
  ];

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
        <div className="h-6 w-6 border-2 border-[var(--text-main)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const pendingItemStatusLabel = pendingStatusChange
    ? STATUS_CONFIGS[pendingStatusChange.item.status]?.label
    : '';
  const pendingTargetStatusLabel = pendingStatusChange
    ? STATUS_CONFIGS[pendingStatusChange.targetStatus]?.label
    : '';

  return (
    <div className="space-y-4" id="procurement-tab-section">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-main)] flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-[var(--text-main)]" />
            Снабжение и закупки ТМЦ
          </h2>
          <p className="text-xs text-[var(--text-sub)]">
            Операционный контроль поставок материалов, оплат счетов и логистики на строительные объекты
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-sub)]">
            Всего ТМЦ: <strong className="font-mono text-[var(--text-main)]">{items.length}</strong> поз.
          </span>
          <span className="text-xs text-[var(--text-muted)]">|</span>
          <span className="text-xs font-mono font-bold text-[var(--text-main)]">
            {formatCurrency(totalSum)}
          </span>
        </div>
      </div>

      {/* 4 Pipeline Stage KPI Cards (Bento-Box) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* 1. Счета на оплате */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--text-sub)]">
            <span className="font-semibold uppercase tracking-wider text-[10px]">1. На согласовании</span>
            <Clock className="h-4 w-4 text-slate-500" />
          </div>
          <div>
            <span className="text-2xl font-bold font-mono text-[var(--text-main)]">{pendingCount}</span>
            <span className="text-xs text-[var(--text-muted)] ml-1.5">счетов</span>
          </div>
          <p className="text-xs font-mono font-semibold text-[var(--text-sub)] truncate">
            {formatCurrency(pendingSum)}
          </p>
          <p className="text-[11px] text-[var(--text-muted)]">Ожидают акцепта директора</p>
        </div>

        {/* 2. Оплачено */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] space-y-2">
          <div className="flex items-center justify-between text-xs text-amber-700 dark:text-amber-400">
            <span className="font-semibold uppercase tracking-wider text-[10px]">2. Оплачено</span>
            <CreditCard className="h-4 w-4 text-amber-500" />
          </div>
          <div>
            <span className="text-2xl font-bold font-mono text-[var(--text-main)]">{paidCount}</span>
            <span className="text-xs text-[var(--text-muted)] ml-1.5">позиций</span>
          </div>
          <p className="text-xs font-mono font-semibold text-amber-700 dark:text-amber-400 truncate">
            {formatCurrency(paidSum)}
          </p>
          <p className="text-[11px] text-[var(--text-muted)]">Готовится к отгрузке поставщиком</p>
        </div>

        {/* 3. В пути */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] space-y-2">
          <div className="flex items-center justify-between text-xs text-blue-700 dark:text-blue-400">
            <span className="font-semibold uppercase tracking-wider text-[10px]">3. Логистика</span>
            <Truck className="h-4 w-4 text-blue-500" />
          </div>
          <div>
            <span className="text-2xl font-bold font-mono text-[var(--text-main)]">{transitCount}</span>
            <span className="text-xs text-[var(--text-muted)] ml-1.5">в пути</span>
          </div>
          <p className="text-xs font-medium text-[var(--text-sub)]">На контроле снабжения</p>
          <p className="text-[11px] text-[var(--text-muted)]">Доставка спецтехникой</p>
        </div>

        {/* 4. На объекте */}
        <div className="bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl p-4 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] space-y-2">
          <div className="flex items-center justify-between text-xs text-emerald-700 dark:text-emerald-400">
            <span className="font-semibold uppercase tracking-wider text-[10px]">4. Доставлено</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div>
            <span className="text-2xl font-bold font-mono text-[var(--text-main)]">{deliveredCount}</span>
            <span className="text-xs text-[var(--text-muted)] ml-1.5">принято</span>
          </div>
          <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Закрыто нарядами</p>
          <p className="text-[11px] text-emerald-600 dark:text-emerald-400">Входной контроль пройден</p>
        </div>
      </div>

      {/* Filters and Search Bar (FE-4.1) */}
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
                placeholder="Поиск по ТМЦ, поставщику, объекту или номеру счета..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] placeholder:text-[var(--text-muted)] min-h-[38px]"
              />
            </div>

            {/* Custom Styled Select for Object Filter (FE-4.1) */}
            <div className="w-full md:w-72">
              <Select
                options={projectOptions}
                value={projectFilter}
                onChange={setProjectFilter}
                size="md"
                className="w-full"
                id="procurement-project-filter"
              />
            </div>
          </div>

          {/* Mobile Status Filter Dropdown (< md) - No Overflow */}
          <div className="md:hidden pt-1 border-t border-[var(--card-border)]">
            <label className="text-[10px] uppercase font-semibold text-[var(--text-muted)] block mb-1">
              Статус поставки:
            </label>
            <Select
              options={[
                { value: 'all', label: `Все позиции (${items.length})` },
                ...(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => ({
                  value: st,
                  label: `${STATUS_CONFIGS[st].label} (${items.filter((i) => i.status === st).length})`,
                })),
              ]}
              value={statusFilter}
              onChange={(val) => setStatusFilter(val as any)}
              size="md"
              className="w-full"
              id="mobile-procurement-status-select"
            />
          </div>

          {/* Status Filter Pills (desktop only >= md) */}
          <div className="hidden md:flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-[var(--card-border)] pb-1 scrollbar-none">
            <span className="text-[11px] uppercase font-semibold text-[var(--text-muted)] whitespace-nowrap mr-1">
              Статус:
            </span>
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1.5 text-xs rounded-xl font-medium transition-colors whitespace-nowrap cursor-pointer min-h-[34px] ${
                statusFilter === 'all'
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                  : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
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
                  className={`px-3 py-1.5 text-xs rounded-xl font-medium transition-colors whitespace-nowrap flex items-center gap-1.5 cursor-pointer min-h-[34px] ${
                    statusFilter === st
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                      : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
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
        {/* ============================================================ */}
        {/* DESKTOP TABLE VIEW (>= 768px): Zebra Striping & High Contrast (FE-1.3) */}
        {/* ============================================================ */}
        <div className="hidden md:block overflow-x-hidden">
          <table className="w-full text-sm table-fixed" id="procurement-table">
            <thead>
              <tr className="bg-[var(--card-subtle)] border-b border-[var(--card-border)] text-xs text-[var(--text-sub)] uppercase font-semibold">
                <th className="text-left px-3 py-3 w-[24%]">
                  Номенклатура ТМЦ
                </th>
                <th className="text-left px-3 py-3 w-[18%]">
                  Объект СМР
                </th>
                <th className="text-left px-3 py-3 w-[16%]">
                  Поставщик и счет
                </th>
                <th className="text-right px-3 py-3 w-[10%]">
                  Объем
                </th>
                <th className="text-right px-3 py-3 w-[12%]">
                  Сумма счета
                </th>
                <th className="text-left px-3 py-3 w-[10%]">
                  Срок поставки
                </th>
                <th className="text-center px-3 py-3 w-[10%] min-w-[170px]">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--card-border)]">
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-[var(--text-muted)] text-sm">
                    Позиций ТМЦ по выбранным фильтрам не найдено
                  </td>
                </tr>
              ) : (
                filteredItems.map((item, index) => {
                  const statusCfg = STATUS_CONFIGS[item.status];
                  const isMenuOpen = activeDropdownId === item.id;
                  // Zebra striping: alternate row backgrounds
                  const isEvenRow = index % 2 === 1;

                  return (
                    <tr
                      key={item.id}
                      className={`transition-colors ${
                        isEvenRow
                          ? 'bg-[var(--card-subtle)]/40 hover:bg-[var(--card-subtle)]/80'
                          : 'bg-[var(--card-bg)] hover:bg-[var(--card-subtle)]/60'
                      }`}
                    >
                      {/* Item Name (High Contrast) */}
                      <td className="px-3 py-3.5 align-middle">
                        <p className="font-semibold text-[var(--text-main)] text-sm leading-snug line-clamp-2" title={item.item_name}>
                          {item.item_name}
                        </p>
                      </td>

                      {/* Project */}
                      <td className="px-3 py-3.5 align-middle">
                        <div className="flex items-center gap-1.5 text-[var(--text-main)]">
                          <Building2 className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                          <span className="text-xs font-medium truncate" title={item.project_name}>
                            {item.project_name}
                          </span>
                        </div>
                      </td>

                      {/* Supplier & Invoice */}
                      <td className="px-3 py-3.5 align-middle">
                        <p className="text-xs font-semibold text-[var(--text-main)] truncate" title={item.supplier}>
                          {item.supplier}
                        </p>
                        {item.invoice_number ? (
                          <p className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5 truncate">
                            {item.invoice_number}
                          </p>
                        ) : (
                          <p className="text-[11px] text-[var(--text-muted)] mt-0.5">Счет согласован</p>
                        )}
                      </td>

                      {/* Quantity */}
                      <td className="px-3 py-3.5 text-right font-mono text-xs text-[var(--text-main)] align-middle">
                        <span className="font-bold">{item.quantity}</span>{' '}
                        <span className="text-[var(--text-sub)] text-[11px]">{item.unit}</span>
                      </td>

                      {/* Amount */}
                      <td className="px-3 py-3.5 text-right font-mono font-bold text-[var(--text-main)] align-middle whitespace-nowrap">
                        {formatCurrency(item.invoice_amount)}
                      </td>

                      {/* Delivery Deadline */}
                      <td className="px-3 py-3.5 align-middle text-xs whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-[var(--text-sub)]">
                          <Calendar className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0" />
                          <span>{formatDate(item.delivery_deadline)}</span>
                        </div>
                      </td>

                      {/* Status Dropdown with ConfirmModal Protection (FE-1.3) */}
                      <td className="px-3 py-3.5 align-middle text-center">
                        <div className="relative inline-block w-full max-w-[170px] text-left procurement-status-dropdown-container">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveDropdownId(isMenuOpen ? null : item.id);
                            }}
                            disabled={updatingId === item.id}
                            className={`w-full px-2.5 py-1.5 rounded-xl border text-xs font-semibold flex items-center justify-between gap-1.5 cursor-pointer shadow-2xs transition-all overflow-hidden ${statusCfg.badgeClass}`}
                          >
                            <span className="flex items-center gap-1.5 min-w-0 truncate">
                              <span className={`w-2 h-2 rounded-full shrink-0 ${statusCfg.dotColor}`} />
                              <span className="truncate whitespace-nowrap">{statusCfg.label}</span>
                            </span>
                            <ChevronDown className="h-3 w-3 opacity-60 ml-0.5 shrink-0" />
                          </button>

                          {isMenuOpen && (
                            <div className="absolute right-0 mt-1.5 w-52 bg-[var(--card-bg)] rounded-2xl shadow-xl border border-[var(--card-border)] py-1.5 z-40 animate-in fade-in zoom-in-95 duration-100">
                              <div className="px-3 py-1 text-[10px] uppercase font-bold text-[var(--text-muted)] border-b border-[var(--card-border)]">
                                Сменить статус:
                              </div>
                              {(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => {
                                const opt = STATUS_CONFIGS[st];
                                const isCurrent = item.status === st;

                                return (
                                  <button
                                    key={st}
                                    type="button"
                                    onClick={() => requestStatusChange(item, st)}
                                    className={`w-full px-3 py-2 text-xs text-left flex items-center justify-between hover:bg-[var(--card-subtle)] transition-colors cursor-pointer ${
                                      isCurrent
                                        ? 'font-bold text-[var(--text-main)] bg-[var(--card-subtle)]'
                                        : 'text-[var(--text-sub)]'
                                    }`}
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className={`w-2 h-2 rounded-full ${opt.dotColor}`} />
                                      <span>{opt.label}</span>
                                    </div>
                                    {isCurrent && (
                                      <CheckCircle2 className="h-3.5 w-3.5 text-[var(--text-main)] shrink-0" />
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

        {/* ============================================================ */}
        {/* MOBILE CARDS VIEW (< 768px): Expandable Accordion Cards (FE-4.2) */}
        {/* ============================================================ */}
        <div className="md:hidden divide-y divide-[var(--card-border)]">
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-sm text-[var(--text-muted)]">
              Позиций ТМЦ по выбранным фильтрам не найдено
            </div>
          ) : (
            filteredItems.map((item) => {
              const statusCfg = STATUS_CONFIGS[item.status];
              const isExpanded = expandedCardIds.has(item.id);
              const isMenuOpen = activeDropdownId === item.id;

              return (
                <div key={item.id} className="p-3.5 transition-colors">
                  {/* Collapsed Header: Tap to expand */}
                  <div
                    onClick={() => toggleCardExpand(item.id)}
                    className="flex items-start justify-between gap-2.5 cursor-pointer select-none"
                    role="button"
                    tabIndex={0}
                  >
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-sm text-[var(--text-main)] leading-snug line-clamp-1">
                          {item.item_name}
                        </span>
                      </div>
                      <p className="text-xs text-[var(--text-sub)] flex items-center gap-1 truncate">
                        <Building2 className="h-3 w-3 text-[var(--text-muted)] shrink-0" />
                        <span className="truncate">{item.project_name}</span>
                      </p>
                      <p className="text-xs font-mono font-bold text-[var(--text-main)]">
                        {formatCurrency(item.invoice_amount)}
                      </p>
                    </div>

                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      {/* Compact badge */}
                      <span className={`px-2 py-0.5 rounded-lg border text-[11px] font-semibold flex items-center gap-1 ${statusCfg.badgeClass}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dotColor}`} />
                        <span>{statusCfg.label}</span>
                      </span>

                      {/* Expand indicator chevron */}
                      <div className="p-1 text-[var(--text-muted)]">
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Accordion Body (FE-4.2) */}
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-[var(--card-border)] space-y-3 animate-in fade-in duration-150">
                      {/* Supplier & Details Grid */}
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                          <span className="text-[10px] uppercase font-medium text-[var(--text-muted)] block">Поставщик</span>
                          <p className="font-semibold text-[var(--text-main)] mt-0.5 truncate">
                            {item.supplier}
                          </p>
                          <p className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5 truncate">
                            {item.invoice_number || 'Счет согласован'}
                          </p>
                        </div>

                        <div className="bg-[var(--card-subtle)] p-2.5 rounded-xl border border-[var(--card-border)]">
                          <span className="text-[10px] uppercase font-medium text-[var(--text-muted)] block">Объем</span>
                          <p className="font-mono font-bold text-[var(--text-main)] text-sm mt-0.5">
                            {item.quantity} <span className="text-xs font-normal text-[var(--text-sub)]">{item.unit}</span>
                          </p>
                          <div className="flex items-center gap-1 text-[11px] text-[var(--text-sub)] mt-0.5">
                            <Calendar className="h-3 w-3 text-[var(--text-muted)] shrink-0" />
                            <span>До {formatDate(item.delivery_deadline)}</span>
                          </div>
                        </div>
                      </div>

                      {/* Actions row: Change Status + Next step button */}
                      <div className="flex items-center justify-between gap-2 pt-1">
                        {/* Change status menu button */}
                        <div className="relative procurement-status-dropdown-container">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveDropdownId(isMenuOpen ? null : item.id);
                            }}
                            className="min-h-[44px] px-3.5 py-2 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-bg)] text-[var(--text-main)] text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-2xs transition-colors"
                          >
                            <span className={`w-2 h-2 rounded-full ${statusCfg.dotColor} shrink-0`} />
                            <span>Сменить статус</span>
                            <ChevronDown className="h-3.5 w-3.5 text-[var(--text-muted)] ml-0.5" />
                          </button>

                          {isMenuOpen && (
                            <div className="absolute left-0 bottom-full mb-1.5 w-52 bg-[var(--card-bg)] rounded-2xl shadow-2xl border border-[var(--card-border)] py-1.5 z-40 animate-in fade-in zoom-in-95 duration-100">
                              <div className="px-3.5 py-1.5 text-[10px] uppercase font-bold text-[var(--text-muted)] border-b border-[var(--card-border)]">
                                Выберите статус:
                              </div>
                              {(Object.keys(STATUS_CONFIGS) as ProcurementStatus[]).map((st) => {
                                const opt = STATUS_CONFIGS[st];
                                return (
                                  <button
                                    key={st}
                                    type="button"
                                    onClick={() => requestStatusChange(item, st)}
                                    className="w-full px-3 py-2 text-xs text-left flex items-center justify-between hover:bg-[var(--card-subtle)] text-[var(--text-main)] min-h-[40px] cursor-pointer"
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className={`w-2 h-2 rounded-full ${opt.dotColor}`} />
                                      <span>{opt.label}</span>
                                    </div>
                                    {item.status === st && (
                                      <CheckCircle2 className="h-3.5 w-3.5 text-[var(--text-main)]" />
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Fast forward next step button */}
                        {statusCfg.nextStatus && (
                          <button
                            type="button"
                            onClick={() => requestStatusChange(item, statusCfg.nextStatus!)}
                            disabled={updatingId === item.id}
                            className="min-h-[44px] px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs"
                          >
                            <span>{statusCfg.nextLabel}</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* ============================================================ */}
      {/* CONFIRMATION MODAL: Protection against accidental status changes (FE-4.3) */}
      {/* ============================================================ */}
      {pendingStatusChange && (
        <ConfirmModal
          isOpen={true}
          title="Смена статуса поставки ТМЦ"
          description={
            <span>
              Подтвердите изменение статуса поставки по счету{' '}
              <strong className="text-[var(--text-main)]">
                {pendingStatusChange.item.invoice_number || '№ б/н'}
              </strong>
              . Позиция:{' '}
              <strong className="text-[var(--text-main)]">
                «{pendingStatusChange.item.item_name}»
              </strong>{' '}
              на объекте {pendingStatusChange.item.project_name}.
            </span>
          }
          currentStatusLabel={pendingItemStatusLabel}
          newStatusLabel={pendingTargetStatusLabel}
          confirmText="Подтвердить смену статуса"
          cancelText="Отмена"
          variant="default"
          isLoading={updatingId === pendingStatusChange.item.id}
          onConfirm={handleConfirmStatusChange}
          onCancel={() => setPendingStatusChange(null)}
        />
      )}
    </div>
  );
}
