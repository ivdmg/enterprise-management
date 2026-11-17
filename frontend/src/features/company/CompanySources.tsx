import { useEffect, useState } from 'react';
import { companyRequest } from '@/api/companySession';
import { useAuth } from '@/context/AuthContext';

interface CompanySource {
  id: string;
  label: string;
  status: 'unchecked' | 'running' | 'current' | 'stale' | 'needs_attention' | 'paused';
  last_success_at: string | null;
  next_attempt_at: string | null;
  error?: { message: string; next_step: string } | null;
}

const states: Record<CompanySource['status'], string> = {
  unchecked: 'Ещё не проверен',
  running: 'Идёт обновление',
  current: 'Актуален',
  stale: 'Данные устарели',
  needs_attention: 'Требует внимания',
  paused: 'Приостановлен',
};

function dateLabel(value: string) {
  return new Date(value).toLocaleString('ru-RU', { timeZoneName: 'short' });
}

export function CompanySources() {
  const { companyProfile } = useAuth();
  const [sources, setSources] = useState<CompanySource[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState<string | null>(null);
  const canRequest = companyProfile?.permissions.includes('company.sources.retry_request');

  useEffect(() => {
    const controller = new AbortController();
    void companyRequest<CompanySource[]>('/company/integrations', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setSources(data); })
      .catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить источники.'); });
    return () => controller.abort();
  }, []);

  async function retry(id: string) {
    setPending(id);
    setError('');
    setNotice('');
    try {
      await companyRequest(`/company/integrations/${encodeURIComponent(id)}/retry-request`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setNotice('Запрос на повтор отправлен в поддержку.');
    } catch {
      setError('Не удалось отправить запрос.');
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="space-y-3">
      <h1 className="text-xl font-semibold">Источники данных</h1>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!sources ? !error && <p role="status">Загрузка…</p> : sources.length ? (
        <ul className="space-y-3">{sources.map(source => (
          <li key={source.id} className="space-y-2 rounded-lg border border-card-border bg-card p-4">
            <h2 className="font-semibold">{source.label}</h2>
            <p>{states[source.status]}</p>
            <p>{source.last_success_at ? <>Последнее успешное обновление <time dateTime={source.last_success_at}>{dateLabel(source.last_success_at)}</time></> : 'Успешных обновлений пока нет.'}</p>
            {source.next_attempt_at && <p>Следующая попытка <time dateTime={source.next_attempt_at}>{dateLabel(source.next_attempt_at)}</time></p>}
            {source.error && <div className="rounded bg-warning-bg p-2 text-warning-text"><p>{source.error.message}</p><p>{source.error.next_step}</p></div>}
            {canRequest && ['stale', 'needs_attention'].includes(source.status) && (
              <button type="button" className="rounded border p-2" disabled={pending !== null} onClick={() => void retry(source.id)}>Запросить повтор</button>
            )}
          </li>
        ))}</ul>
      ) : <p>Подключённых источников нет.</p>}
    </section>
  );
}
