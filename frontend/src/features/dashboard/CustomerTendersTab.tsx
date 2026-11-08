import { Pagination } from '@/components/Pagination';
import { motion, useReducedMotion } from 'motion/react';
import { DataLoading } from '@/components/DataLoading';
import { flattenDrive, useDriveCatalog } from '@/features/files/DriveCatalog';
import { useAuth } from '@/context/AuthContext';
import { FieldBeam } from '@/components/FieldBeam';
import { Activity, ArrowRight, ArrowUpRight, CalendarClock, CircleAlert, Database, FileText, Scale, Search, Workflow } from 'lucide-react';
import { lazy, Suspense, useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { demoMode } from '@/api/mode';
import { Select } from '@/components/Select';
import type { DriveSyncStatus } from '@/types';

type SourceRow = { source_row: number; values: (string | number | null)[] };
export type CustomerTender = {
  id: string; number: string; amount: number | null; link: string | null; curator?: string | null;
  source_name?: string;
  source_warnings: Record<string, string[]>; registry: SourceRow | null; monitoring: SourceRow | null;
  registry_columns: string[]; monitoring_columns: string[];
};
export type TenderView = 'summary' | 'registry' | 'sources';
type Filter = 'all' | 'critical' | 'soon' | 'review';
type Signal = { kind: Exclude<Filter, 'all'>; label: string; date?: string };

const labels = {
  summary: ['Где горит?', 'Сроки, документы и риски по контрактам.'],
  registry: ['Контракты', 'Реестр контрактов, сроки исполнения и контроль документов.'],
  sources: ['Источники данных', 'Подключённые листы и качество импорта.'],
};
const filters: Record<Filter, string> = { all: 'Все записи', critical: 'Критические сроки', soon: 'От 4 до 7 дней', review: 'Проверить документы' };
const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const syncFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Astrakhan' });
const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 });
const day = 86_400_000;
const OverviewCharts = lazy(() => import('./OverviewCharts').then(module => ({ default: module.OverviewCharts })));

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
  return <a className="workspace-sheet-link" href={href} target="_blank" rel="noreferrer">Открыть Google Таблицу <ArrowUpRight size={16} /></a>;
}

export function CustomerTendersTab({ view, onViewChange, penalties, onOpenAlerts, onOpenProcurement, onOpenFinance }: {
  view: TenderView;
  onViewChange: (view: TenderView) => void;
  penalties: number | null;
  onOpenAlerts: () => void;
  onOpenProcurement: () => void;
  onOpenFinance: () => void;
}) {
  const { user } = useAuth();
  const canReadCatalog = !demoMode && (user?.role === 'manager' || user?.role === 'admin');
  const { nodes: catalog, error: catalogError } = useDriveCatalog(view === 'sources' && canReadCatalog);
  const unconnected = flattenDrive(catalog ?? []).filter(node => !node.active_source);
  const reducedMotion = useReducedMotion();
  const [rows, setRows] = useState<CustomerTender[] | null>(null);
  const [error, setError] = useState('');
  const [request, setRequest] = useState(0);
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [engineers, setEngineers] = useState<import('./EngineerDocumentsTab').EngineerRegister | null>(null);
  const [sync, setSync] = useState<DriveSyncStatus | null>(null);

  useEffect(() => {
    let current = true;
    apiClient.getCustomerTenders().then(data => { if (current) setRows(data); })
      .catch(() => { if (current) setError('Не удалось загрузить данные.'); });
    return () => { current = false; };
  }, [request]);

  useEffect(() => {
    if (view !== 'registry') {
      setFilter('all');
      setFocusedId(null);
    }
    setSearch('');
    setPage(0);
  }, [view]);

  useEffect(() => {
    if (view !== 'sources') return;
    let current = true;
    apiClient.getDriveSyncStatus().then(status => { if (current) setSync(status); })
      .catch(() => { if (current) setSync(null); });
    const controller = new AbortController();
    if (!demoMode) apiClient.getEngineerDocuments(controller.signal)
      .then(data => { if (current) setEngineers(data.register); })
      .catch(() => {});
    return () => { current = false; controller.abort(); };
  }, [view]);

  const today = Date.parse(new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Astrakhan', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  const records = (rows ?? []).map(row => ({ row, flags: signals(row, today) }));
  const count = (kind: Filter) => records.filter(({ flags }) => flags.some(flag => flag.kind === kind)).length;
  const source = rows?.find(row => row.link)?.link;
  const syncedAt = Date.parse(sync?.last_synced_at ?? '');
  const registryCount = records.filter(({ row }) => row.registry).length;
  const statusCounts = new Map<string, number>();
  if (view === 'summary') for (const { row } of records) {
    if (!row.registry) continue;
    const status = field(row.registry, 16) || 'Без статуса';
    statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
  }
  const statuses = [...statusCounts].sort((a, b) => b[1] - a[1]);
  const statusChart = statuses.slice(0, 3).map(([name, value]) => ({ name, value }));
  if (statuses.length > 3) statusChart.push({ name: 'Остальные', value: statuses.slice(3).reduce((sum, [, value]) => sum + value, 0) });
  const deadlineCount = records.filter(({ row }) => dateValue(field(row.registry, 18)) !== null).length;
  const monitoringCount = records.filter(({ row }) => row.monitoring).length;
  const warningCount = records.reduce((sum, { row }) => sum + Object.values(row.source_warnings ?? {}).reduce((n, warnings) => n + warnings.length, 0), 0);
  const filtered = records.filter(({ row, flags }) =>
    (focusedId === null || row.id === focusedId) &&
    (row.registry || row.monitoring) &&
    (filter === 'all' || flags.some(flag => flag.kind === filter)) &&
    [row.number, field(row.registry, 9), field(row.registry, 1), field(row.monitoring, 1), field(row.registry, 3), field(row.monitoring, 3)]
      .join(' ').toLocaleLowerCase('ru').includes(search.trim().toLocaleLowerCase('ru')),
  ).sort((a, b) => filter !== 'all'
    ? Number(Boolean(b.flags.length)) - Number(Boolean(a.flags.length)) ||
      (a.flags.find(flag => flag.date)?.date ?? '9999').localeCompare(b.flags.find(flag => flag.date)?.date ?? '9999')
    : 0);

  const pageSize = 12;
  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / pageSize) - 1));

  function openContracts(next: Filter, id: string | null = null) {
    setPage(0);
    setFilter(next);
    setFocusedId(id);
    onViewChange('registry');
  }

  return <div key={view} className="workspace-reveal">
    {view !== 'summary' && <header className={'workspace-heading workspace-pagebar' + (view === 'registry' ? ' workspace-contract-heading' : '')}>
      <div><div className="workspace-eyebrow"><span /> УПРАВЛЕНИЕ ТЕНДЕРАМИ</div><h1>{labels[view][0]}</h1><p>{labels[view][1]}</p></div>
      {view === 'registry' && rows && rows.length > 0 && <div className="workspace-contract-controls">
        <FieldBeam className="workspace-search-beam"><label className="workspace-search"><Search size={18} /><input aria-label="Поиск по записям" placeholder="Заказчик, город или номер" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} /></label></FieldBeam>
        <Select ariaLabel="Фильтр по сигналам" className="workspace-filter" value={filter} options={Object.entries(filters).map(([value, label]) => ({ value, label }))} onChange={value => { setFilter(value as Filter); setFocusedId(null); setPage(0); }} />
        <p className="workspace-result">Найдено: {filtered.length}</p>
        <SourceLink href={source} />
        {focusedId && <button className="workspace-link workspace-contract-reset" onClick={() => openContracts('all')}>Показать весь список</button>}
      </div>}
    </header>}

    {error ? <div className="workspace-panel" role="alert">{error} <button className="workspace-link" onClick={() => { setError(''); setRequest(value => value + 1); }}>Повторить</button></div>
      : rows === null ? <DataLoading className="workspace-panel" />
      : !rows.length ? <div className="workspace-panel">Импортированных записей пока нет.</div>
      : view === 'summary' ? <>
        <motion.div className="workspace-metrics" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: reducedMotion ? 0 : 0.13 } } }}>
          {[
            { icon: CircleAlert, title: 'Критические риски', value: deadlineCount ? count('critical') : '—',
              stats: [['Просрочено', deadlineCount ? records.filter(({ flags }) => flags.some(flag => flag.kind === 'critical' && flag.date && Date.parse(flag.date) < today)).length : '—'],
                ['До трёх дней', deadlineCount ? records.filter(({ flags }) => flags.some(flag => flag.kind === 'critical' && flag.date && Date.parse(flag.date) >= today)).length : '—']],
              action: () => openContracts('critical') },
            { icon: CalendarClock, title: 'Предупреждения', value: deadlineCount ? count('soon') : '—',
              stats: [['Горизонт', '4–7 дней'], ['Даты в реестре', deadlineCount]], action: () => openContracts('soon') },
            { icon: Scale, title: 'Штрафы и неустойки', value: penalties === null ? '—' : money.format(penalties),
              stats: [['Источник', 'Журнал рисков'], ['Статус', 'Открытые']], action: onOpenAlerts },
            { icon: FileText, title: 'Проверить документы', value: count('review'),
              stats: [['Реестр', registryCount], ['Мониторинг', monitoringCount]], action: () => openContracts('review') },
          ].map(({ icon: Icon, title, value, stats, action }) => (
            <motion.article key={title} className="workspace-kpi" variants={{ hidden: { opacity: reducedMotion ? 1 : 0, y: reducedMotion ? 0 : 16 }, visible: { opacity: 1, y: 0, transition: { duration: reducedMotion ? 0 : 0.34 } } }}>
              <div className="workspace-kpi-body">
                <div className="workspace-kpi-title"><span><Icon size={17} /></span>{title}</div>
                <strong>{value}</strong>
                <dl>{stats.map(([label, detail]) => <div key={label}><dt>{label}</dt><dd>{detail}</dd></div>)}</dl>
              </div>
              <button type="button" className="workspace-round-action" onClick={action} aria-label={title}><ArrowUpRight size={16} /></button>
            </motion.article>
          ))}
        </motion.div>
        <Suspense fallback={<DataLoading className="workspace-panel mt-4" />}>
          <OverviewCharts statuses={statusChart} onFinance={onOpenFinance} onRegistry={() => onViewChange('registry')}
            obligations={records.flatMap(({ row, flags }) => {
              const signal = flags.find(flag => flag.date);
              return signal?.date ? [{
                id: row.id, title: field(row.registry, 9) || field(row.registry, 1) || row.number,
                subtitle: row.curator || field(row.registry, 1), date: signal.date, label: signal.label,
                action: () => openContracts(signal.kind, row.id),
              }] : [];
            }).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 4)}
            onMonitoring={() => openContracts('all')} />
        </Suspense>
        <div className="workspace-section-heading workspace-section-spaced"><h2>Контроль данных</h2></div>
        <div className="workspace-overview">
          <section className="workspace-panel"><FileText size={20} /><h2>Проверить документы</h2><p>{count('review')} записей с отметкой о работах и пустыми полями документов</p><button className="workspace-link" onClick={() => openContracts('review')}>К записям <ArrowRight size={16} /></button></section>
          <section className="workspace-panel"><Workflow size={20} /><h2>Контракты</h2><p>{registryCount} записей в реестре · {monitoringCount} в мониторинге</p><button className="workspace-link" onClick={() => onViewChange('registry')}>К карточкам контрактов <ArrowRight size={16} /></button></section>
          <section className="workspace-panel"><Database size={20} /><h2>Качество данных</h2><p>{warningCount ? `Строк с ошибкой формулы в номере: ${warningCount}` : 'Ошибок формул в импортируемых номерах нет'}</p><button className="workspace-link" onClick={() => onViewChange('sources')}>Об источнике <ArrowRight size={16} /></button></section>
        </div>
        <div className="workspace-section-heading workspace-section-spaced"><h2>Операции</h2></div>
        <section className="workspace-panel mt-4"><h2>Снабжение и закупки</h2><p>Счета на оплате с просроченной или близкой датой поставки.</p><button className="workspace-link" onClick={onOpenProcurement}>К счетам с риском по сроку <ArrowRight size={16} /></button></section>
      </> : view === 'sources' ? <div className="workspace-sources"><section className="workspace-panel">
        <Database size={24} /><h2>{demoMode ? 'Учебный реестр' : rows?.find(row => row.source_name)?.source_name ?? 'Тендеры · Google Drive'}</h2>
        <p>{demoMode ? 'Синтетические данные в браузере. Google Drive в этом режиме отключён.' : 'Связь по внутреннему номеру. Изменения вносятся в исходный документ.'}</p>
        <p>{sync?.status === 'error' ? 'Последняя попытка синхронизации завершилась ошибкой.' : sync?.status === 'syncing' ? 'Идёт синхронизация.' : null}</p>
        {!demoMode && <p>{Number.isFinite(syncedAt) ? `Последняя синхронизация · ${syncFormat.format(syncedAt)}` : 'Время последней синхронизации недоступно.'}</p>}
        <dl className="workspace-facts workspace-source-facts"><div><dt>Реест Ольга</dt><dd>{registryCount} записей</dd></div><div><dt>Ежедневный мониторинг</dt><dd>{monitoringCount} записей</dd></div></dl>
        <SourceLink href={source} />
        {warningCount > 0 && <p className="workspace-warning">Пропущено строк с ошибкой формулы во внутреннем номере: {warningCount}. После исправления в источнике они попадут в следующий импорт.</p>}
      </section>
        {engineers && <section className="workspace-panel">
          <FileText size={24} /><h2>Документы инженеров</h2>
          <p>Матрица сотрудников и файлы из папки «удостоверения».</p>
          <dl className="workspace-facts workspace-source-facts"><div><dt>Сотрудники в реестре</dt><dd>{engineers.people.length}</dd></div></dl>
          <p>Последняя синхронизация · {syncFormat.format(new Date(engineers.synced_at))}</p>
          <SourceLink href={engineers.source_url} />
        </section>}
        {canReadCatalog && <section className="workspace-panel">
          <h2>Файлы без парсера</h2>
          <p>Эти файлы доступны в каталоге. У них нет самостоятельного импорта данных.</p>
          {catalogError ? <p role="alert">{catalogError}</p> : !catalog ? <DataLoading /> :
            unconnected.length ? <details className="workspace-unconnected">
              <summary>Показать файлы · {unconnected.length}</summary>
              <ul>{unconnected.map(node => <li key={node.id}>
                <a href={node.url} target="_blank" rel="noreferrer">{node.name}</a>
                <small>Парсер не подключён</small>
              </li>)}</ul>
            </details> : <p>Все файлы подключены.</p>}
        </section>}
      </div> : <>
        {!filtered.length && <div className="workspace-panel">{search ? 'По вашему запросу ничего не найдено.' : (filter === 'critical' || filter === 'soon') && !deadlineCount ? 'В реестре нет дат исполнения для оценки сроков.' : 'Записей по этому фильтру нет.'}</div>}
        <div className="workspace-records">
          {filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize).map(({ row, flags }) => {
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
                <div><dt>Сумма контракта</dt><dd>{row.amount === null ? 'Не указана' : money.format(row.amount)}</dd></div>
                {row.curator && <div><dt>Куратор</dt><dd>{row.curator}</dd></div>}
                {row.monitoring && <div><dt>Отметки о работах</dt><dd>{workNotes.length ? workNotes.join(', ') : 'Не указаны'}</dd></div>}
              </dl>

              <SourceLink href={row.link} />
            </article>;
          })}
        </div>
        <Pagination page={currentPage} total={filtered.length} pageSize={pageSize} onPage={next => {
          setPage(next);
          window.scrollTo(0, 0);
        }} />
      </>}
  </div>;
}
