import { useEffect, useState } from 'react';
import { apiClient } from '@/api/client';
import { browserMockMode } from '@/api/mode';
import { Card } from '@/components/Card';
import { Select } from '@/components/Select';

export type MonthlySchedule = {
  link: string | null;
  records: {
    row: number;
    code: string;
    customer: string | null;
    work: string | null;
    city: string | null;
    frequency: string | null;
    work_type: string | null;
    status: string | null;
    assignee: string | null;
    entries: Record<string, string | number | boolean>;
  }[];
};

export function MonthlyDispatch() {
  const [schedule, setSchedule] = useState<MonthlySchedule | null>(null);
  const [error, setError] = useState(false);
  const [month, setMonth] = useState('');
  const [mobileLimit, setMobileLimit] = useState(12);
  useEffect(() => {
    if (browserMockMode) return;
    const controller = new AbortController();
    apiClient.getMonthlyDispatch(controller.signal).then(setSchedule).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => controller.abort();
  }, []);

  if (error) return <p role="alert">Не удалось загрузить помесячный график.</p>;
  if (!schedule) return null;
  const months = [...new Set(schedule.records.flatMap(record =>
    Object.keys(record.entries).map(day => day.slice(0, 7)),
  ))].sort();
  const monthFormat = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const visible = schedule.records.filter(record =>
    !month || Object.keys(record.entries).some(day => day.startsWith(month)),
  );
  return (
    <Card className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Помесячный график · {visible.length}</h2>
        {schedule.link && <a className="workspace-catalog-button" href={schedule.link} target="_blank" rel="noreferrer">Открыть график на Диске</a>}
      </div>
      {months.length ? <Select ariaLabel="Месяц отметки" value={month} onChange={value => {
        setMonth(value);
        setMobileLimit(12);
      }} options={[
        { value: '', label: 'Все месяцы' },
        ...months.map(value => ({ value, label: monthFormat.format(new Date(`${value}-01T00:00:00Z`)) })),
      ]} /> : <p className="text-sm text-[var(--text-sub)]">В исходной книге нет отметок по датам.</p>}
      <div className="hidden md:block max-h-[32rem] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[var(--text-sub)]">
            <tr>{['Вн. №', 'Заказчик и объект', 'Работы', 'Статус', 'Ответственный', 'Отметки в графике'].map(title =>
              <th className="p-2 align-top" key={title}>{title}</th>,
            )}</tr>
          </thead>
          <tbody>{visible.map(record => (
            <tr key={record.row} className="border-t border-[var(--card-border)] align-top">
              <td className="p-2">{record.code}</td>
              <td className="p-2">{record.customer}{[record.work, record.city].filter(Boolean).map((value, index) =>
                <div key={index} className="text-[var(--text-sub)]">{value}</div>,
              )}</td>
              <td className="p-2">{[record.work_type, record.frequency].filter(Boolean).join(' · ') || '—'}</td>
              <td className="p-2">{record.status ?? '—'}</td>
              <td className="p-2">{record.assignee ?? '—'}</td>
              <td className="p-2">{Object.entries(record.entries).filter(([day]) => !month || day.startsWith(month)).map(([day, value]) =>
                <div key={day}>{day.split('-').reverse().join('.')} · {String(value)}</div>,
              )}{!Object.keys(record.entries).length && '—'}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="md:hidden space-y-2">
        {visible.slice(0, mobileLimit).map(record => (
          <details key={record.row} className="workspace-dispatch-record">
            <summary>
              <span className="workspace-dispatch-record-heading">
                <strong>{record.customer ?? record.work ?? record.code}</strong>
                <small>{[record.code, record.city, record.status].filter(Boolean).join(' · ')}</small>
              </span>
            </summary>
            <dl>
              {([['Объект', record.work], ['Работы', [record.work_type, record.frequency].filter(Boolean).join(' · ')],
                ['Ответственный', record.assignee]] as const).filter(([, value]) => value).map(([label, value]) =>
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              )}
              {Object.entries(record.entries).filter(([day]) => !month || day.startsWith(month)).map(([day, value]) => (
                <div key={day}><dt>{day.split('-').reverse().join('.')}</dt><dd>{String(value)}</dd></div>
              ))}
            </dl>
          </details>
        ))}
        {visible.length > mobileLimit && <button type="button" className="workspace-catalog-button"
          onClick={() => setMobileLimit(limit => limit + 12)}>Показать ещё · {visible.length - mobileLimit}</button>}
      </div>
      {!visible.length && <p className="text-sm text-[var(--text-sub)]">В графике нет записей.</p>}
    </Card>
  );
}
