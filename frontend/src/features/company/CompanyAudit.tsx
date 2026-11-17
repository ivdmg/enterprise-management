import { useEffect, useState, type FormEvent } from 'react';
import { companyRequest } from '@/api/companySession';

interface AuditEvent {
  id: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  result: string;
  changes: Record<string, unknown> | null;
  created_at: string;
}

const actionLabels: Record<string, string> = {
  status_changed: 'Изменение статуса',
  created: 'Создание',
  uploaded: 'Загрузка файла',
  parsed: 'Разбор файла',
  deleted: 'Удаление',
  previewed: 'Предпросмотр',
  downloaded: 'Скачивание',
  settings_updated: 'Изменение настроек',
};

export function CompanyAudit({ base }: { base: string }) {
  const [filter, setFilter] = useState('');
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    const controller = new AbortController();
    void companyRequest<AuditEvent[]>(`/company/audit?page=${page}&limit=${pageSize}${filter ? '&' + filter : ''}`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setEvents(data); setError(false); } })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [filter, page]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    for (const name of ['action', 'entity_type', 'from', 'to']) {
      const value = String(fields.get(name) ?? '').trim();
      if (!value) continue;
      next.set(name, name === 'from' || name === 'to' ? new Date(value).toISOString() : value);
    }
    const value = next.toString();
    if (value !== filter || page !== 1) {
      setEvents(null);
      setError(false);
      setFilter(value);
      setPage(1);
    }
  }

  function movePage(offset: number) {
    setEvents(null);
    setError(false);
    setPage(value => value + offset);
  }

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-5">
      <a className="underline" href={base}>Вернуться в кабинет</a>
      <h1 className="text-xl font-semibold">Журнал действий</h1>
      <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
        <label className="grid gap-1">Действие <select className="rounded border p-1" name="action">
          <option value="">Все</option>
          {Object.entries(actionLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
        <label className="grid gap-1">Тип объекта <input className="rounded border p-1" name="entity_type" /></label>
        <label className="grid gap-1">С <input className="rounded border p-1" type="datetime-local" name="from" /></label>
        <label className="grid gap-1">По <input className="rounded border p-1" type="datetime-local" name="to" /></label>
        <button className="rounded border p-1">Применить</button>
      </form>
      {error ? <p role="alert">Не удалось загрузить журнал.</p> : !events ? <p role="status">Загрузка…</p> : (
        events.length ? <ul className="space-y-3">{events.map(item => (
          <li className="rounded border border-card-border p-3" key={item.id}>
            <p>{item.actor_name} · {actionLabels[item.action] ?? item.action}</p>
            <p className="text-sm">{item.entity_type} · {new Date(item.created_at).toLocaleString('ru-RU')}</p>
            {item.changes && Object.keys(item.changes).length > 0 && (
              <details className="text-sm"><summary>Детали изменения</summary>
                <pre className="whitespace-pre-wrap break-words">{JSON.stringify(item.changes, null, 2)}</pre>
              </details>
            )}
          </li>
        ))}</ul> : <p>Записей по заданным условиям нет.</p>
      )}
      <nav aria-label="Страницы журнала" className="flex gap-4">
        <button disabled={page === 1 || !events} onClick={() => movePage(-1)}>Назад</button>
        <span>Страница {page}</span>
        <button disabled={events?.length !== pageSize} onClick={() => movePage(1)}>Дальше</button>
      </nav>
    </main>
  );
}
