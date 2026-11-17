import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { OperationsPanel } from './OperationsPanel';
import type { IncidentState, IncidentSummary, IntegrationStatus } from './operationsTypes';
import { platformPost, platformRequest, PlatformRequestError, type Operator } from './platformApi';

interface CompanySummary {
  id: string;
  code: string;
  name: string;
  state: 'draft' | 'active' | 'paused' | 'closed';
  health: 'healthy' | 'degraded' | 'unknown';
  modules: { id: string; label: string }[];
  integration_count: number;
  last_success_at: string | null;
  open_incident_count: number;
  version: number;
}

interface PlatformStatus {
  status: string;
  worker_heartbeat_at: string | null;
  queue_depth: number;
  active_incident_count: number;
}

interface AuditRow {
  id: string;
  actor_id: string;
  action: string;
  company_id: string | null;
  result: string;
  created_at: string;
}

interface RunSummary {
  id: string;
  mode: 'preview' | 'import';
  state: string;
  adapter_version: string;
  request_id: string | null;
  created_at: string;
  rows_processed: number | null;
  warning_count: number | null;
}

interface IntegrationEvent {
  id: string;
  code: string;
  message: string;
  next_step: string;
  run_id: string;
  request_id: string | null;
  created_at: string;
}

const companyStates = { draft: 'Черновик', active: 'Активна', paused: 'Приостановлена', closed: 'Закрыта' };
const healthLabels = { healthy: 'Работает', degraded: 'Есть проблемы', unknown: 'Состояние неизвестно' };
const companyTransitions: Record<CompanySummary['state'], string[]> = {
  draft: ['active'], active: ['paused'], paused: ['active', 'closed'], closed: [],
};
const incidentTransitions: Record<IncidentState, { value: IncidentState; label: string }[]> = {
  new: [{ value: 'in_progress', label: 'Взять в работу' }],
  in_progress: [{ value: 'escalated', label: 'Передать разработчику' }, { value: 'verifying', label: 'Начать проверку' }],
  escalated: [{ value: 'verifying', label: 'Начать проверку' }],
  verifying: [{ value: 'closed', label: 'Закрыть' }],
  closed: [{ value: 'in_progress', label: 'Открыть снова' }],
};
const field = 'rounded-md border border-card-border bg-card px-2 py-1 disabled:opacity-50';
const card = 'space-y-2 rounded-xl border border-card-border bg-card p-4';
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const dateText = (value: string | null) => value ? new Date(value).toLocaleString('ru-RU', { timeZoneName: 'short' }) : 'Нет данных';

type Result<T> = { state: 'loading' } | { state: 'error' } | { state: 'ready'; data: T; updatedAt: string };
function useRead<T>(path: string, revision = 0): Result<T> {
  const [snapshot, setSnapshot] = useState<{ path: string; revision: number; result: Result<T> }>();
  useEffect(() => {
    const controller = new AbortController();
    void platformRequest<T>(path, { signal: controller.signal })
      .then(data => {
        if (!controller.signal.aborted) setSnapshot({ path, revision, result: { state: 'ready', data, updatedAt: new Date().toISOString() } });
      })
      .catch(() => { if (!controller.signal.aborted) setSnapshot({ path, revision, result: { state: 'error' } }); });
    return () => controller.abort();
  }, [path, revision]);
  return snapshot?.path === path && snapshot.revision === revision ? snapshot.result : { state: 'loading' };
}

function Read<T>({ result, children }: { result: Result<T>; children: (data: T) => ReactNode }) {
  if (result.state === 'loading') return <p role="status">Загрузка…</p>;
  if (result.state === 'error') return <p role="alert">Не удалось загрузить данные.</p>;
  return <>{children(result.data)}</>;
}

function useCommand() {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const active = useRef(false);
  const last = useRef<{ fingerprint: string; key: string } | null>(null);

  async function run(path: string, body: object, success: string, onSuccess?: (data: unknown) => void, method = "POST") {
    if (active.current) return;
    const fingerprint = method + path + JSON.stringify(body);
    if (last.current?.fingerprint !== fingerprint) last.current = { fingerprint, key: crypto.randomUUID() };
    active.current = true;
    setPending(true);
    setError('');
    setMessage('');
    try {
      const data = method === 'POST' ? await platformPost(path, body, last.current.key)
        : await platformRequest(path, { method, body: JSON.stringify(body) });
      last.current = null;
      setMessage(success);
      onSuccess?.(data);
    } catch (failure) {
      const status = failure instanceof PlatformRequestError ? failure.status : 0;
      if (failure instanceof PlatformRequestError && failure.code === 'COMPANY_NOT_READY') {
        setError('Опубликуйте конфигурацию, подтвердите источники и пригласите директора перед активацией.');
        last.current = null;
      } else if (status === 409) {
        setError('Состояние изменилось. Перечитайте данные перед повтором.');
        last.current = null;
      } else if (status === 403) {
        setError('Недостаточно прав для этой операции.');
      } else {
        setError('Не удалось выполнить операцию. Попробуйте ещё раз.');
      }
    } finally {
      active.current = false;
      setPending(false);
    }
  }

  return { pending, error, message, run };
}

function CommandStatus({ command }: { command: ReturnType<typeof useCommand> }) {
  return <>{command.error && <p role="alert">{command.error}</p>}{command.message && <p role="status">{command.message}</p>}</>;
}

function readForm(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  const fields = new FormData(event.currentTarget);
  return (key: string) => String(fields.get(key) ?? '').trim();
}

export function PlatformCompanies({ operator }: { operator: Operator }) {
  const [query, setQuery] = useState('');
  const [revision, setRevision] = useState(0);
  const status = useRead<PlatformStatus>('/status', revision);
  const companies = useRead<CompanySummary[]>('/companies' + (query ? '?' + query : ''), revision);
  const command = useCommand();

  return (
    <>
      <h1 className="text-2xl font-semibold">Компании</h1>
      <section className={card} aria-label="Состояние платформы">
        <h2 className="font-semibold">Платформа</h2>
        <Read result={status}>{data => (
          <p>Состояние {healthLabels[data.status as keyof typeof healthLabels] ?? data.status} · Очередь {data.queue_depth} · Последний сигнал воркера {dateText(data.worker_heartbeat_at)}</p>
        )}</Read>
      </section>
      <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
        const read = readForm(event);
        const params = new URLSearchParams();
        for (const key of ['search', 'health', 'state']) if (read(key)) params.set(key, read(key));
        setQuery(params.toString());
      }}>
        <label className="grid">Компания <input className={field} name="search" /></label>
        <label className="grid">Состояние <select className={field} name="state"><option value="">Все</option>
          {Object.entries(companyStates).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label className="grid">Работа сервиса <select className={field} name="health"><option value="">Любая</option>
          {Object.entries(healthLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <button className={field}>Применить</button>
        <button className={field} type="button" onClick={() => setRevision(value => value + 1)}>Обновить</button>
      </form>
      <Read result={companies}>{items => items.length ? (
        <ul className="grid gap-3 md:grid-cols-2">{items.map(item => (
          <li className={card} key={item.id}>
            <Link className="font-semibold underline" to={`/platform/companies/${encodeURIComponent(item.id)}`}>{item.name}</Link>
            <p>{companyStates[item.state]} · {healthLabels[item.health]}</p>
            <p>Источники {item.integration_count} · Открытые инциденты {item.open_incident_count}</p>
            <p>Последнее успешное обновление {dateText(item.last_success_at)}</p>
            <p>{item.modules.map(module => module.label).join(', ') || 'Модули не подключены'}</p>
          </li>
        ))}</ul>
      ) : <p>Компаний по заданным условиям нет.</p>}</Read>
      {operator.role === 'owner' && (
        <form className={card} onSubmit={event => {
          const read = readForm(event);
          void command.run('/companies', { code: read('code'), name: read('name') }, 'Черновик создан.', () => setRevision(value => value + 1));
        }}>
          <h2 className="font-semibold">Создать компанию</h2>
          <div className="flex flex-wrap items-end gap-2">
            <label className="grid">Код <input className={field} name="code" required /></label>
            <label className="grid">Название <input className={field} name="name" required /></label>
            <button className={field} disabled={command.pending}>Создать черновик</button>
          </div>
          <CommandStatus command={command} />
        </form>
      )}
    </>
  );
}

export function PlatformCompany({ operator }: { operator: Operator }) {
  const { id, '*': subpath = '' } = useParams();
  if (!id) return <p>Компания недоступна.</p>;
  return <CompanyDetails key={id + '/' + subpath} id={id} subpath={subpath} operator={operator} />;
}

function CompanyDetails({ id, subpath, operator }: { id: string; subpath: string; operator: Operator }) {
  const [revision, setRevision] = useState(0);
  const path = `/companies/${encodeURIComponent(id)}`;
  const base = '/platform' + path;
  const company = useRead<CompanySummary>(path, revision);
  const command = useCommand();
  const reload = () => setRevision(value => value + 1);
  const [area, recordId] = subpath.split('/');

  return (
    <>
      <Link className="underline" to="/platform/companies">Все компании</Link>
      <Read result={company}>{item => (
        <>
          <h1 className="text-2xl font-semibold">{item.name}</h1>
          <p>{companyStates[item.state]} · {healthLabels[item.health]}</p>
          <nav className="flex flex-wrap gap-3" aria-label="Разделы компании">
            <Link className="underline" to={base}>Обзор</Link>
            <Link className="underline" to={base + '/invitations'}>Приглашения</Link>
            {operator.role === 'owner' && <Link className="underline" to={base + '/config'}>Настройка</Link>}
          </nav>
          {area === 'integrations' && recordId ? <IntegrationDetails path={path} id={recordId} operator={operator} />
            : area === 'incidents' && recordId ? <IncidentDetails path={path} id={recordId} />
              : area === 'invitations' ? <CompanyInvitations path={path} operator={operator} />
                : area === 'config' && operator.role === 'owner' ? <CompanyConfig path={path} />
                  : !area ? <CompanyOperations path={path} base={base} operator={operator} /> : <p>Раздел недоступен.</p>}
          {!area && operator.role === 'owner' && companyTransitions[item.state].length > 0 && (
            <form className={card} onSubmit={event => {
              const read = readForm(event);
              const to = read('to');
              if (to === 'closed' && !window.confirm('Закрыть компанию? Восстановить её из панели будет нельзя.')) return;
              void command.run(path + '/transitions', { version: item.version, to, reason: read('reason') }, 'Состояние компании изменено.', reload);
            }}>
              <h2 className="font-semibold">Изменить состояние компании</h2>
              <label>Новое состояние <select className={field} name="to">
                {companyTransitions[item.state].map(state => <option key={state} value={state}>{companyStates[state as keyof typeof companyStates]}</option>)}
              </select></label>
              <label> Причина <input className={field} name="reason" required /></label>
              <button className={field} disabled={command.pending}>Подтвердить</button>
              <CommandStatus command={command} />
            </form>
          )}
        </>
      )}</Read>
    </>
  );
}

function CompanyOperations({ path, base, operator }: { path: string; base: string; operator: Operator }) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState('');
  const integrations = useRead<IntegrationStatus[]>(path + '/integrations', revision);
  const incidents = useRead<IncidentSummary[]>(path + '/incidents' + (state ? '?state=' + state : ''), revision);
  const toSection = <T,>(result: Result<T[]>) => result.state === 'ready'
    ? { state: 'ready' as const, items: result.data, updatedAt: result.updatedAt }
    : result;

  return (
    <section className="space-y-3">
      <button className={field} onClick={() => setRevision(value => value + 1)}>Обновить</button>
      <label className="ml-2">Инциденты <select className={field} value={state} onChange={event => setState(event.target.value)}>
        <option value="">Все</option><option value="new">Новые</option><option value="in_progress">В работе</option>
        <option value="escalated">Переданы разработчику</option><option value="verifying">На проверке</option><option value="closed">Закрытые</option>
      </select></label>
      {operator.role === "owner" && <IntegrationEditor path={path} reload={() => setRevision(value => value + 1)} />}
      <OperationsPanel
        integrations={toSection(integrations)}
        incidents={toSection(incidents)}
        timeZone={timeZone}
        integrationHref={id => base + '/integrations/' + encodeURIComponent(id)}
        incidentHref={id => base + '/incidents/' + encodeURIComponent(id)}
      />
    </section>
  );
}

function IntegrationDetails({ path, id, operator }: { path: string; id: string; operator: Operator }) {
  const [revision, setRevision] = useState(0);
  const [approvedPreviewId, setApprovedPreviewId] = useState<string | null>(null);
  const integration = useRead<IntegrationStatus>(path + '/integrations/' + encodeURIComponent(id), revision);
  const runs = useRead<RunSummary[]>(path + '/runs?integration_id=' + encodeURIComponent(id), revision);
  const events = useRead<IntegrationEvent[]>(path + '/events?integration_id=' + encodeURIComponent(id), revision);
  const command = useCommand();
  const reload = () => setRevision(value => value + 1);

  return <Read result={integration}>{source => {
    return (
      <section className={card}>
        <h2 className="text-lg font-semibold">{source.label}</h2>
        <p>Адаптер {source.adapter_id} · Версия {source.adapter_version}</p>
        <p>Последнее успешное обновление {dateText(source.last_success_at)}</p>
        {operator.role === "owner" && <IntegrationEditor path={path} source={source} reload={reload} />}
        {source.error && <><p>{source.error.message}</p><p>{source.error.next_step}</p></>}
        {source.status !== 'paused' && (
          <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
            const read = readForm(event);
            const mode = read('mode');
            const approved_preview_id = read('approved_preview_id') || undefined;
            void command.run(path + '/integrations/' + encodeURIComponent(id) + '/runs', {
              mode, reason: read('reason'), expected_integration_version: source.version, approved_preview_id,
            }, 'Запуск принят в очередь.', reload);
          }}>
            <label className="grid">Операция <select className={field} name="mode">
              <option value="import">Повторить импорт</option><option value="preview">Предпросмотр</option>
            </select></label>
            <label className="grid">Причина <input className={field} name="reason" required /></label>
            <label className="grid">ID подтверждённого предпросмотра <input key={approvedPreviewId} className={field} name="approved_preview_id" defaultValue={approvedPreviewId ?? undefined} /></label>
            <button className={field} disabled={command.pending}>Поставить в очередь</button>
          </form>
        )}
        <CommandStatus command={command} />
        <h3 className="font-semibold">История запусков</h3>
        <Read result={runs}>{items => items.length ? <ul className="space-y-2">{items.map(item => (
          <li key={item.id} className="border-t border-card-border pt-2">
            <p>{item.mode === 'preview' ? 'Предпросмотр' : 'Импорт'} · {item.state} · {dateText(item.created_at)}</p>
            <p className="text-sm break-all">Запуск {item.id} · Строк {item.rows_processed ?? '—'} · Предупреждений {item.warning_count ?? '—'}</p>
            {operator.role === 'owner' && item.mode === 'preview' && item.state === 'succeeded' && (
              <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
                const read = readForm(event);
                void command.run(path + '/runs/' + encodeURIComponent(item.id) + '/approve', {
                  expected_integration_version: source.version, reason: read('reason'),
                }, 'Предпросмотр подтверждён.', data => {
                  if (data && typeof data === 'object' && 'approved_preview_id' in data
                    && typeof data.approved_preview_id === 'string') setApprovedPreviewId(data.approved_preview_id);
                  reload();
                });
              }}>
                <label className="grid">Подтверждение директора <input className={field} name="reason" required /></label>
                <button className={field} disabled={command.pending}>Подтвердить предпросмотр</button>
              </form>
            )}
          </li>
        ))}</ul> : <p>Запусков пока нет.</p>}</Read>
        <h3 className="font-semibold">Операционные события</h3>
        <Read result={events}>{items => items.length ? (
          <ul className="space-y-2">{items.map(event => <li key={event.id} className="border-t border-card-border pt-2">
            <p>{event.message} · {dateText(event.created_at)}</p>
            <p>{event.next_step}</p>
            <p className="break-all text-sm">{event.code} · Запуск {event.run_id}{event.request_id && ' · Запрос ' + event.request_id}</p>
          </li>)}</ul>
        ) : <p>Событий пока нет.</p>}</Read>
      </section>
    );
  }}</Read>;
}

function IncidentDetails({ path, id }: { path: string; id: string }) {
  const [revision, setRevision] = useState(0);
  const incidentPath = path + '/incidents/' + encodeURIComponent(id);
  const incident = useRead<IncidentSummary>(incidentPath, revision);
  const command = useCommand();
  const [copyStatus, setCopyStatus] = useState('');
  return <Read result={incident}>{item => (
    <section className={card}>
      <h2 className="text-lg font-semibold">{item.message}</h2>
      <p>{item.impact}</p>
      <p>{item.next_step}</p>
      <p>Открыт {dateText(item.opened_at)} · Обновлён {dateText(item.updated_at)}</p>
      <button className={field} onClick={async () => {
        try {
          await navigator.clipboard.writeText([item.code, item.opened_at, item.run_id].filter(Boolean).join('\n'));
          setCopyStatus('Сводка скопирована.');
        } catch { setCopyStatus('Не удалось скопировать сводку.'); }
      }}>Скопировать сводку для разработчика</button>
      {copyStatus && <p role="status">{copyStatus}</p>}
      {incidentTransitions[item.state]?.length > 0 && <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
        const read = readForm(event);
        void command.run(incidentPath + '/transitions', {
          version: item.version, to: read('to'), reason: read('reason'),
        }, 'Инцидент обновлён.', () => setRevision(value => value + 1));
      }}>
        <label className="grid">Действие <select className={field} name="to">{incidentTransitions[item.state].map(action => (
          <option key={action.value} value={action.value}>{action.label}</option>
        ))}</select></label>
        <label className="grid">Причина <input className={field} name="reason" required /></label>
        <button className={field} disabled={command.pending}>Сохранить</button>
      </form>}
      <CommandStatus command={command} />
    </section>
  )}</Read>;
}

export function PlatformOwnerAudit() {
  const [page, setPage] = useState(1);
  const rows = useRead<AuditRow[]>('/audit?page=' + page + '&limit=20');
  return (
    <>
      <h1 className="text-2xl font-semibold">История действий поддержки</h1>
      <Read result={rows}>{items => items.length ? (
        <ul className="space-y-2">{items.map(item => <li className={card} key={item.id}>
          <p>{item.action} · {item.result} · {dateText(item.created_at)}</p><p>Оператор {item.actor_id} {item.company_id && '· Компания ' + item.company_id}</p>
        </li>)}</ul>
      ) : <p>Записей нет.</p>}</Read>
      <div className="flex gap-3">
        <button className={field} disabled={page === 1} onClick={() => setPage(value => value - 1)}>Назад</button>
        <span>Страница {page}</span>
        <button className={field} disabled={rows.state !== 'ready' || rows.data.length < 20} onClick={() => setPage(value => value + 1)}>Дальше</button>
      </div>
    </>
  );
}

interface AccessRequestRow {
  id: string;
  email?: string;
  role: string;
  state: string;
}
interface InvitationRow {
  id: string;
  email?: string;
  role: string;
  state: string;
  delivery_state: string;
  expires_at: string;
  version: number;
}

function CompanyInvitations({ path, operator }: { path: string; operator: Operator }) {
  const [revision, setRevision] = useState(0);
  const requests = useRead<AccessRequestRow[]>(path + '/access-requests?state=pending', revision);
  const invitations = useRead<InvitationRow[]>(path + '/invitations', revision);
  const command = useCommand();
  const reload = () => setRevision(value => value + 1);
  return (
    <section className={card}>
      <h2 className="text-lg font-semibold">Приглашения</h2>
      <CommandStatus command={command} />
      <Read result={requests}>{items => items.length ? <ul className="space-y-2">{items.map(item => (
        <li key={item.id} className="flex flex-wrap items-center gap-2">
          <span>{item.email ?? item.id} · {item.role}</span>
          <button className={field} disabled={command.pending} onClick={() => void command.run(
            path + '/invitations', { access_request_id: item.id }, 'Приглашение оформлено.', reload,
          )}>Оформить приглашение</button>
        </li>
      ))}</ul> : <p>Новых заявок нет.</p>}</Read>
      {operator.role === 'owner' && <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
        const read = readForm(event);
        void command.run(path + '/invitations', { email: read('email'), full_name: read('full_name'), role: 'admin' }, 'Приглашение директору оформлено.', reload);
      }}>
        <label className="grid">Почта директора <input className={field} name="email" type="email" required /></label>
        <label className="grid">Имя <input className={field} name="full_name" required /></label>
        <button className={field} disabled={command.pending}>Пригласить директора</button>
      </form>}
      <h3 className="font-semibold">История приглашений</h3>
      <Read result={invitations}>{items => items.length ? <ul className="space-y-2">{items.map(item => (
        <li key={item.id} className="space-y-2 border-t border-card-border pt-2">
          <p>{item.email ?? item.id} · {item.state} · {item.delivery_state} · До {dateText(item.expires_at)}</p>
          {['pending', 'expired'].includes(item.state) && (
            <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
              const read = readForm(event);
              void command.run(path + '/invitations/' + encodeURIComponent(item.id) + '/' + read('operation'),
                { version: item.version, reason: read('reason') }, 'Приглашение обновлено.', reload);
            }}>
              <label className="grid">Действие <select name="operation" className={field}><option value="reissue">Перевыпустить</option>
                {item.state === 'pending' && <option value="revoke">Отозвать</option>}</select></label>
              <label className="grid">Причина <input className={field} name="reason" required /></label>
              <button className={field} disabled={command.pending}>Подтвердить</button>
            </form>
          )}
        </li>
      ))}</ul> : <p>Приглашений пока нет.</p>}</Read>
    </section>
  );
}

interface ConfigRevision {
  revision: number;
  state: string;
  modules: { id: string; label?: string; order: number; enabled: boolean; settings?: Record<string, unknown> }[];
  catalog: Record<string, string>;
  revisions: { revision: number; state: string }[];
}
function CompanyConfig({ path }: { path: string }) {
  const [revision, setRevision] = useState(0);
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const command = useCommand();
  const config = useRead<ConfigRevision>(path + '/config', revision);
  const configPath = path + '/config/revisions';

  return <Read result={config}>{current => (
    <section className={card}>
      <h2 className="text-lg font-semibold">Настройка модулей</h2>
      <p>Текущая ревизия {current.revision}</p>
      <p>Доступные ревизии {current.revisions.map(item => item.revision).join(", ") || "—"}</p>
      <form key={current.revision} className="space-y-2" onSubmit={event => {
        const read = readForm(event);
        const modules = Object.keys(current.catalog).map((id, index) => {
          const previous = current.modules.find(module => module.id === id);
          return { id, enabled: read('enabled-' + id) === 'on', label: read('label-' + id) || undefined,
            order: Number(read('order-' + id) || index), settings: previous?.settings };
        });
        void command.run(configPath, { base_revision: current.revision, modules }, 'Черновик сохранён.', data => {
          if (data && typeof data === 'object' && 'revision' in data && typeof data.revision === 'number') setDraftRevision(data.revision);
        });
      }}>
        {Object.keys(current.catalog).map((id, index) => {
          const previous = current.modules.find(module => module.id === id);
          return <div key={id} className="flex flex-wrap items-center gap-2">
            <label><input type="checkbox" name={'enabled-' + id} defaultChecked={previous?.enabled ?? false} /> {current.catalog[id] ?? id}</label>
            <label>Название <input className={field} name={'label-' + id} defaultValue={previous?.label} /></label>
            <label>Порядок <input className={field} type="number" min="0" name={'order-' + id} defaultValue={previous?.order ?? index} /></label>
          </div>;
        })}
        <button className={field} disabled={command.pending}>Сохранить черновик</button>
      </form>
      <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
        const read = readForm(event);
        void command.run(configPath + '/' + Number(read('revision')) + '/' + read('operation'),
          { expected_active_revision: current.revision, reason: read('reason') }, 'Конфигурация обновлена.', () => {
            setDraftRevision(null);
            setRevision(value => value + 1);
          });
      }}>
        <label className="grid">Операция <select className={field} name="operation"><option value="publish">Опубликовать</option><option value="rollback">Откатить</option></select></label>
        <label className="grid">Ревизия <input key={draftRevision} className={field} name="revision" type="number" min="1" defaultValue={draftRevision ?? undefined} required /></label>
        <label className="grid">Причина <input className={field} name="reason" required /></label>
        <button className={field} disabled={command.pending}>Подтвердить</button>
      </form>
      <CommandStatus command={command} />
    </section>
  )}</Read>;
}

function IntegrationEditor({ path, source, reload }: { path: string; source?: IntegrationStatus; reload: () => void }) {
  const command = useCommand();
  const [provider, setProvider] = useState(source?.type ?? 'google_drive');
  return (
    <details className="rounded border border-card-border p-3">
      <summary>{source ? 'Настроить источник' : 'Подключить источник'}</summary>
      <form key={source?.version} className="grid gap-2 py-3" onSubmit={event => {
        const read = readForm(event);
        const source_ref = read('source_ref') || undefined;
        const secret_ref = read('secret_ref') || undefined;
        const schedule = read('schedule') ? Number(read('schedule')) : undefined;
        const fields = {
          label: read('label'), adapter_version: read('adapter_version'),
          source_ref, secret_ref, schedule,
          stale_after_seconds: Number(read('stale_after_seconds')),
          enabled: read('enabled') === 'on',
        };
        if (source) {
          void command.run(path + '/integrations/' + encodeURIComponent(source.id),
            { ...fields, version: source.version }, 'Настройки сохранены.', reload, 'PATCH');
        } else {
          const adapter_id = read('adapter_id');
          void command.run(path + '/integrations', {
            ...fields, type: provider, adapter_id,
            module_id: adapter_id === 'customer_tenders' ? 'projects' : 'tasks',
          }, 'Источник подключён.', reload);
        }
      }}>
        {!source && <>
          <label className="grid">Тип <select className={field} value={provider} onChange={event => setProvider(event.target.value)}>
            <option value="google_drive">Google Drive</option><option value="test_workbook">Локальная книга стенда</option>
          </select></label>
          <label className="grid">Адаптер <select className={field} name="adapter_id">
            <option value="customer_tenders">Реестр тендеров</option><option value="equipment_registry">Реестр оборудования</option>
          </select></label>
        </>}
        <label className="grid">Название <input className={field} name="label" defaultValue={source?.label} required /></label>
        <label className="grid">Версия адаптера <input className={field} name="adapter_version" defaultValue={source?.adapter_version ?? 'v1'} required /></label>
        <label className="grid">Идентификатор источника <input className={field} name="source_ref" required={!source} autoComplete="off" /></label>
        {provider === 'google_drive' && <label className="grid">Ссылка на секрет <input className={field} name="secret_ref" required={!source} autoComplete="off" /></label>}
        <label className="grid">Интервал импорта, сек <input className={field} name="schedule" type="number" min="60" max="86400" /></label>
        <label className="grid">Порог устаревания, сек <input className={field} name="stale_after_seconds" type="number" min="60" max="604800"
          defaultValue={source?.stale_after_seconds ?? 900} required /></label>
        <label><input name="enabled" type="checkbox" defaultChecked={source?.status !== 'paused'} /> Источник включён</label>
        <button className={field} disabled={command.pending}>Сохранить</button>
      </form>
      <CommandStatus command={command} />
    </details>
  );
}
