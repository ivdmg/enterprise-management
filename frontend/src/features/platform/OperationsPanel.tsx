import { useId, type ReactNode } from 'react';
import type { IncidentState, IncidentSummary, IntegrationState, IntegrationStatus } from './operationsTypes';

type SectionData<T> =
  | { state: 'loading' }
  | { state: 'error' }
  | { state: 'ready'; items: readonly T[]; updatedAt: string; outdated?: boolean };

interface OperationsPanelProps {
  integrations: SectionData<IntegrationStatus>;
  incidents: SectionData<IncidentSummary>;
  timeZone: string;
  integrationHref: (id: string) => string;
  incidentHref: (id: string) => string;
}

const integrationLabels: Record<IntegrationState, string> = {
  unchecked: 'Ещё не проверен',
  running: 'В работе',
  current: 'Актуален',
  stale: 'Данные устарели',
  needs_attention: 'Требует вмешательства',
  paused: 'Приостановлен',
};

const incidentLabels: Record<IncidentState, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  escalated: 'Передан разработчику',
  verifying: 'На проверке',
  closed: 'Закрыт',
};

const severityLabels = new Map([
  ['info', 'Информация'],
  ['warning', 'Предупреждение'],
  ['error', 'Ошибка'],
  ['critical', 'Критический'],
]);

function Status({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-card-subtle-border bg-card-subtle px-2.5 py-1 text-xs font-semibold">
      {children}
    </span>
  );
}

function DateValue({ value, format }: { value: string | null; format: Intl.DateTimeFormat }) {
  if (!value) return <>Нет данных</>;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return <>Нет данных</>;

  return <time dateTime={value}>{format.format(date)}</time>;
}

interface OperationsSectionProps<T> {
  title: string;
  data: SectionData<T>;
  emptyMessage: string;
  format: Intl.DateTimeFormat;
  renderItem: (item: T) => ReactNode;
}

function OperationsSection<T extends { id: string }>({
  title,
  data,
  emptyMessage,
  format,
  renderItem,
}: OperationsSectionProps<T>) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} aria-busy={data.state === 'loading'} className="min-w-0 space-y-3">
      <h2 id={headingId} className="text-lg font-semibold">{title}</h2>
      {data.state === 'loading' && <p role="status">Загрузка…</p>}
      {data.state === 'error' && <p role="alert">Не удалось загрузить раздел. Попробуйте обновить страницу.</p>}
      {data.state === 'ready' && (
        <>
          {data.outdated && (
            <p role="status" className="rounded-lg bg-warning-bg p-3 text-sm text-warning-text">
              Обновление недоступно. Показано состояние от <DateValue value={data.updatedAt} format={format} />.
            </p>
          )}
          {data.items.length ? (
            <ul className="space-y-3">
              {data.items.map((item) => (
                <li key={item.id} className="space-y-2 rounded-xl border border-card-border bg-card p-4 break-words">
                  {renderItem(item)}
                </li>
              ))}
            </ul>
          ) : <p>{emptyMessage}</p>}
        </>
      )}
    </section>
  );
}

export function OperationsPanel({ integrations, incidents, timeZone, integrationHref, incidentHref }: OperationsPanelProps) {
  const format = new Intl.DateTimeFormat('ru-RU', {
    timeZone,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  });

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <OperationsSection
        title="Источники"
        data={integrations}
        emptyMessage="Подключённых источников нет."
        format={format}
        renderItem={(source) => (
          <>
            <h3 className="font-semibold">
              <a href={integrationHref(source.id)} className="underline underline-offset-4">{source.label}</a>
            </h3>
            <Status>{integrationLabels[source.status]}</Status>
            <dl className="grid gap-1 text-sm">
              <div>
                <dt className="inline">Последнее успешное обновление </dt>
                <dd className="inline"><DateValue value={source.last_success_at} format={format} /></dd>
              </div>
              {source.next_attempt_at && (
                <div>
                  <dt className="inline">Следующая попытка </dt>
                  <dd className="inline"><DateValue value={source.next_attempt_at} format={format} /></dd>
                </div>
              )}
            </dl>
            {source.error && (
              <div className="space-y-1 rounded-lg bg-warning-bg p-3 text-sm text-warning-text">
                <p>{source.error.message}</p>
                <p>{source.error.next_step}</p>
              </div>
            )}
          </>
        )}
      />
      <OperationsSection
        title="Инциденты"
        data={incidents}
        emptyMessage="По текущим условиям инцидентов нет."
        format={format}
        renderItem={(incident) => (
          <>
            <h3 className="font-semibold">
              <a href={incidentHref(incident.id)} className="underline underline-offset-4">{incident.message}</a>
            </h3>
            <div className="flex flex-wrap gap-2">
              <Status>{incidentLabels[incident.state]}</Status>
              <Status>{severityLabels.get(incident.severity) ?? 'Уровень не определён'}</Status>
            </div>
            <p className="text-sm">{incident.impact}</p>
            <p className="text-sm"><strong>Следующий шаг</strong> {incident.next_step}</p>
            <p className="text-xs"><DateValue value={incident.updated_at} format={format} /> · {incident.code}</p>
          </>
        )}
      />
    </div>
  );
}
