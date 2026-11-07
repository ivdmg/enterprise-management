import { Activity, ArrowRight, ArrowUpRight, CalendarClock, CircleAlert, Database, FileText, Scale, Search, Workflow } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { Select } from '@/components/Select';
import type { DriveSyncStatus } from '@/types';

type SourceRow = { source_row: number; values: (string | number | null)[] };
export type CustomerTender = {
  id: string; number: string; amount: number | null; link: string | null; curator?: string | null;
  source_warnings: Record<string, string[]>; registry: SourceRow | null; monitoring: SourceRow | null;
  registry_columns: string[]; monitoring_columns: string[];
};
export type TenderView = 'summary' | 'registry' | 'monitoring' | 'sources';
type Filter = 'all' | 'critical' | 'soon' | 'review';
type Signal = { kind: Exclude<Filter, 'all'>; label: string; date?: string };

const labels = {
  summary: ['Где горит?', 'Сроки, документы и риски по контрактам.'],
  registry: ['Контракты', 'Заказчики, статусы и сроки из реестра.'],
  monitoring: ['Документы и сроки', 'Контроль исполнения и отметок о документах.'],
  sources: ['Источники данных', 'Подключённые листы и качество импорта.'],
};
const filters: Record<Filter, string> = { all: 'Все записи', critical: 'Критические сроки', soon: 'От 4 до 7 дней', review: 'Проверить документы' };
const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const syncFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Astrakhan' });
const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 });
const day = 86_400_000;

function field(row: SourceRow | null, index: number) {
  const value = row?.values[index];
  if (value == null) return '';
  const text = String(value).trim();
  return text.startsWith('#') ? '' : text;
}

function dateValue(value: string) {
  const local = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
  if (local) value = `${local[3]}-${local[2]}-${local[1]}`;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value ? timestamp : null;
}

function signals(row: CustomerTender, today: number): Signal[] {
  const deadline = field(row.registry, 18);
  const timestamp = dateValue(deadline);
  const status = field(row.registry, 16).toLowerCase().replaceAll('ё', 'е');
  if (/^(завершен|исполнен|расторгнут|отменен)(?:\s|$)/.test(status)) return [];

  const periods = [4, 11, 18];
  const needsReview = periods.some(index =>
    field(row.monitoring, index) &&
    ![1, 2, 3, 4].some(offset => field(row.monitoring, index + offset)),
  );
  const result: Signal[] = [];
  // The template has one contractual deadline. Only assess it against missing
  // documentary evidence when the work period is unambiguous.
  const usedPeriods = periods.filter(index => Array.from({ length: 7 }, (_, offset) => field(row.monitoring, index + offset)).some(Boolean));
  if (timestamp !== null && usedPeriods.length <= 1 &&
      !usedPeriods.some(index => [1, 2, 3, 4].some(offset => field(row.monitoring, index + offset)))) {
    const remaining = (timestamp - today) / day;
    const date = new Date(timestamp).toISOString().slice(0, 10);
    if (remaining <= 3) result.push({ kind: 'critical', label: remaining < 0 ? 'Срок истёк' : remaining === 0 ? 'Срок сегодня' : `До срока: ${remaining} дн.`, date });
    else if (remaining <= 7) result.push({ kind: 'soon', label: `До срока: ${remaining} дн.`, date });
  }
  if (needsReview) result.push({ kind: 'review', label: 'Нет отметки о документах' });
  return result;
}

function SourceLink({ href }: { href: string | null | undefined }) {
  if (!href || !/^https:\/\/(?:docs|drive)\.google\.com\//i.test(href)) return null;
  return <a className="workspace-link" href={href} target="_blank" rel="noreferrer">Открыть Google Таблицу <ArrowUpRight size={16} /></a>;
}

export function CustomerTendersTab({ view, onViewChange, penalties, onOpenAlerts, onOpenProcurement }: {
  view: TenderView;
  onViewChange: (view: TenderView) => void;
  penalties: number | null;
  onOpenAlerts: () => void;
  onOpenProcurement: () => void;
}) {
  const [rows, setRows] = useState<CustomerTender[] | null>(null);
  const [error, setError] = useState('');
  const [request, setRequest] = useState(0);
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(12);
  const [sync, setSync] = useState<DriveSyncStatus | null>(null);

  useEffect(() => {
    let current = true;
    apiClient.getCustomerTenders().then(data => { if (current) setRows(data); })
      .catch(() => { if (current) setError('Не удалось загрузить данные.'); });
    return () => { current = false; };
  }, [request]);

  useEffect(() => {
    if (view !== 'monitoring') setFilter('all');
    setSearch('');
    setLimit(12);
  }, [view]);

  useEffect(() => {
    if (view !== 'sources') return;
    let current = true;
    apiClient.getDriveSyncStatus().then(status => { if (current) setSync(status); })
      .catch(() => { if (current) setSync(null); });
    return () => { current = false; };
  }, [view]);

  const today = Date.parse(new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Astrakhan', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  const records = (rows ?? []).map(row => ({ row, flags: signals(row, today) }));
  const count = (kind: Filter) => records.filter(({ flags }) => flags.some(flag => flag.kind === kind)).length;
  const source = rows?.find(row => row.link)?.link;
  const syncedAt = Date.parse(sync?.last_synced_at ?? '');
  const registryCount = records.filter(({ row }) => row.registry).length;
  const deadlineCount = records.filter(({ row }) => dateValue(field(row.registry, 18)) !== null).length;
  const monitoringCount = records.filter(({ row }) => row.monitoring).length;
  const warningCount = records.reduce((sum, { row }) => sum + Object.values(row.source_warnings ?? {}).reduce((n, warnings) => n + warnings.length, 0), 0);
  const monitoring = view === 'monitoring';
  const filtered = records.filter(({ row, flags }) =>
    (monitoring ? row.monitoring || flags.length : row.registry) &&
    (filter === 'all' || flags.some(flag => flag.kind === filter)) &&
    [row.number, field(row.registry, 9), field(row.registry, 1), field(row.monitoring, 1), field(row.registry, 3), field(row.monitoring, 3)]
      .join(' ').toLocaleLowerCase('ru').includes(search.trim().toLocaleLowerCase('ru')),
  ).sort((a, b) => monitoring
    ? Number(Boolean(b.flags.length)) - Number(Boolean(a.flags.length)) ||
      (a.flags.find(flag => flag.date)?.date ?? '9999').localeCompare(b.flags.find(flag => flag.date)?.date ?? '9999')
    : 0);

  function openMonitoring(next: Filter) {
    setFilter(next);
    onViewChange('monitoring');
  }

  return <>
    <header className="workspace-heading">
      <div><div className="workspace-eyebrow"><span /> УПРАВЛЕНИЕ ТЕНДЕРАМИ</div><h1>{labels[view][0]}</h1><p>{labels[view][1]}</p></div>
      <SourceLink href={source} />
    </header>

    {error ? <div className="workspace-panel" role="alert">{error} <button className="workspace-link" onClick={() => { setError(''); setRequest(value => value + 1); }}>Повторить</button></div>
      : rows === null ? <div className="workspace-panel" role="status">Загружаем сводку…</div>
      : !rows.length ? <div className="workspace-panel">Импортированных записей пока нет.</div>
      : view === 'summary' ? <>
        <div className="workspace-section-heading">
          <h2>Контроль обязательств</h2>
          <p>{deadlineCount ? `Даты исполнения: ${deadlineCount} из ${registryCount}` : 'Сроки исполнения в реестре не заполнены'}</p>
        </div>
        <div className="workspace-metrics">
          {([
            ['critical', CircleAlert, 'Критические риски', 'Просрочено или осталось до 3 дней'],
            ['soon', CalendarClock, 'Предупреждения', 'До срока исполнения осталось 4–7 дней'],
          ] as const).map(([kind, Icon, label, description]) => (
            <button className={`workspace-metric ${kind}`} key={kind} onClick={() => openMonitoring(kind)}>
              <span className="metric-icon"><Icon size={20} /></span><ArrowRight className="metric-arrow" size={19} />
              <strong>{deadlineCount ? count(kind) : '—'}</strong>
              <b>{label}</b><small>{description}</small>
            </button>
          ))}
          <button className="workspace-metric" onClick={onOpenAlerts}>
            <span className="metric-icon"><Scale size={20} /></span><ArrowRight className="metric-arrow" size={19} />
            <strong>{penalties === null ? '—' : money.format(penalties)}</strong><b>Штрафы и неустойки</b><small>{penalties === null ? 'Нет записей с рассчитанной суммой' : 'По открытым уведомлениям о нарушении срока'}</small>
          </button>
        </div>
        <div className="workspace-section-heading workspace-section-spaced"><h2>Контроль данных</h2></div>
        <div className="workspace-overview">
          <section className="workspace-panel"><FileText size={20} /><h2>Проверить документы</h2><p>{count('review')} записей с отметкой о работах и пустыми полями документов</p><button className="workspace-link" onClick={() => openMonitoring('review')}>К записям <ArrowRight size={16} /></button></section>
          <section className="workspace-panel"><Workflow size={20} /><h2>Контракты</h2><p>{registryCount} записей в реестре · {monitoringCount} в мониторинге</p><button className="workspace-link" onClick={() => onViewChange('registry')}>К карточкам контрактов <ArrowRight size={16} /></button></section>
          <section className="workspace-panel"><Database size={20} /><h2>Качество данных</h2><p>{warningCount ? `Строк с ошибкой формулы в номере: ${warningCount}` : 'Ошибок формул в импортируемых номерах нет'}</p><button className="workspace-link" onClick={() => onViewChange('sources')}>Об источнике <ArrowRight size={16} /></button></section>
        </div>
        <div className="workspace-section-heading workspace-section-spaced"><h2>Операции</h2></div>
        <section className="workspace-panel mt-4"><h2>Снабжение и закупки</h2><p>Счета на оплате с просроченной или близкой датой поставки.</p><button className="workspace-link" onClick={onOpenProcurement}>К счетам с риском по сроку <ArrowRight size={16} /></button></section>
      </> : view === 'sources' ? <section className="workspace-panel">
        <Database size={24} /><h2>Тендеры · Google Drive</h2>
        <p>Связь по внутреннему номеру. Изменения вносятся в исходный документ.</p>
        <p>{sync?.status === 'error' ? 'Последняя попытка синхронизации завершилась ошибкой.' : sync?.status === 'syncing' ? 'Идёт синхронизация.' : null}</p>
        <p>{Number.isFinite(syncedAt) ? `Последняя синхронизация · ${syncFormat.format(syncedAt)}` : 'Время последней синхронизации недоступно.'}</p>
        <dl className="workspace-facts"><div><dt>Реест Ольга</dt><dd>{registryCount} записей</dd></div><div><dt>Ежедневный мониторинг</dt><dd>{monitoringCount} записей</dd></div></dl>
        {warningCount > 0 && <p className="workspace-warning">Пропущено строк с ошибкой формулы во внутреннем номере: {warningCount}. После исправления в источнике они попадут в следующий импорт.</p>}
        <SourceLink href={source} />
      </section> : <>
        <div className="workspace-controls">
          <label className="workspace-search"><Search size={18} /><input aria-label="Поиск по записям" placeholder="Заказчик, город или номер" value={search} onChange={e => { setSearch(e.target.value); setLimit(12); }} /></label>
          {monitoring && <Select ariaLabel="Фильтр по сигналам" className="workspace-filter" value={filter} options={Object.entries(filters).map(([value, label]) => ({ value, label }))} onChange={value => { setFilter(value as Filter); setLimit(12); }} />}
        </div>
        <p className="workspace-result">Найдено: {filtered.length}</p>
        {!filtered.length && <div className="workspace-panel">{search ? 'По вашему запросу ничего не найдено.' : (filter === 'critical' || filter === 'soon') && !deadlineCount ? 'В реестре нет дат исполнения для оценки сроков.' : 'Записей по этому фильтру нет.'}</div>}
        <div className="workspace-records">
          {filtered.slice(0, limit).map(({ row, flags }) => {
            const work = field(row.registry, 9);
            const customer = field(row.registry, 1) || field(row.monitoring, 1);
            const city = field(row.registry, 3) || field(row.monitoring, 3);
            const deadline = dateValue(field(row.registry, 18));
            const workNotes = [4, 11, 18].map(index => field(row.monitoring, index)).filter(Boolean);
            return <article className="workspace-panel workspace-record" key={row.id}>
              <div className="workspace-record-meta">№ {row.number}{city && ` · ${city}`}</div>
              <h2>{work || customer || 'Запись без названия'}</h2>
              {work && customer && <p>{customer}</p>}
              {flags.map(flag => <span key={flag.kind} className={`workspace-badge ${flag.kind}`}>{flag.label}</span>)}
              <dl className="workspace-facts">
                <div><dt>Статус</dt><dd>{field(row.registry, 16) || 'Не указан'}</dd></div>
                <div><dt>Срок исполнения</dt><dd>{deadline === null ? 'Не указан' : dateFormat.format(deadline)}</dd></div>
                {monitoring && <div><dt>Куратор</dt><dd>{row.curator || 'Не указан'}</dd></div>}
                {monitoring ? <div><dt>Отметки о работах</dt><dd>{workNotes.length ? workNotes.join(', ') : 'Не указаны'}</dd></div>
                  : <div><dt>Сумма контракта</dt><dd>{row.amount === null ? 'Не указана' : money.format(row.amount)}</dd></div>}
              </dl>
              <details><summary>Где искать в источнике</summary>
                {row.registry && <p>Реест Ольга · строка {row.registry.source_row}</p>}
                {row.monitoring && <p>Ежедневный мониторинг · строка {row.monitoring.source_row}</p>}
              </details>
              <SourceLink href={row.link} />
            </article>;
          })}
        </div>
        {filtered.length > limit && <button className="workspace-link workspace-more" onClick={() => setLimit(value => value + 12)}>Показать ещё <ArrowRight size={16} /></button>}
      </>}
  </>;
}
