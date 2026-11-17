import { useEffect, useState, type FormEvent } from 'react';
import { platformPost, platformRequest, PlatformRequestError, type Operator } from './platformApi';

type OperatorRow = Omit<Operator, 'permissions'> & { is_active: boolean };
const field = 'rounded-md border border-card-border bg-card px-2 py-1 disabled:opacity-50';

export function PlatformOperators({ currentId }: { currentId: string }) {
  const [items, setItems] = useState<OperatorRow[] | null>(null);
  const [revision, setRevision] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    void platformRequest<OperatorRow[]>('/operators', { signal: controller.signal }).then(rows => {
      if (!controller.signal.aborted) { setItems(rows); setLoadError(false); }
    }).catch(() => { if (!controller.signal.aborted) setLoadError(true); });
    return () => controller.abort();
  }, [revision]);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const read = (name: string) => String(fields.get(name) ?? '').trim();
    setError('');
    setMessage('');
    setPending(true);
    try {
      await platformPost('/operators', { full_name: read('full_name'), email: read('email'), role: read('role') });
      form.reset();
      setMessage('Приглашение отправлено.');
      setRevision(value => value + 1);
    } catch (failure) {
      setError(failure instanceof PlatformRequestError && failure.status === 409
        ? 'Учётная запись с этим адресом уже существует.'
        : 'Не удалось отправить приглашение.');
    } finally {
      setPending(false);
    }
  }

  async function changeStatus(item: OperatorRow) {
    if (item.is_active && !window.confirm('Отключить оператора и отозвать его сессии?')) return;
    setError('');
    setMessage('');
    setPending(true);
    try {
      const updated = await platformRequest<{ id: string; is_active: boolean }>(
        '/operators/' + encodeURIComponent(item.id),
        { method: 'PATCH', body: JSON.stringify({ is_active: !item.is_active }) },
      );
      setItems(previous => previous?.map(row => row.id === updated.id ? { ...row, is_active: updated.is_active } : row) ?? []);
      setMessage('Состояние доступа изменено.');
    } catch (failure) {
      setError(failure instanceof PlatformRequestError && failure.status === 409
        ? 'Сменить состояние сейчас нельзя. Проверьте, что оператор принял приглашение.'
        : 'Не удалось изменить доступ.');
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Операторы платформы</h1>
      {loadError ? <p role="alert">Не удалось загрузить список операторов.</p>
        : !items ? <p role="status">Загружаем список…</p>
          : <ul className="space-y-2">{items.map(item => (
            <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-card-border bg-card p-3" key={item.id}>
              <span><strong>{item.full_name}</strong> · {item.email} · {item.role === 'owner' ? 'Владелец' : 'Поддержка'} · {item.is_active ? 'Активен' : 'Отключён или приглашён'}</span>
              {item.id !== currentId && (
                <button type="button" className={field} disabled={pending} onClick={() => void changeStatus(item)}>
                  {item.is_active ? 'Отключить' : 'Включить'}
                </button>
              )}
            </li>
          ))}</ul>}
      <form className="space-y-3 rounded-lg border border-card-border bg-card p-4" onSubmit={invite}>
        <h2 className="text-lg font-semibold">Пригласить оператора</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid">Имя <input className={field} name="full_name" autoComplete="name" required /></label>
          <label className="grid">Почта <input className={field} name="email" type="email" autoComplete="email" required /></label>
          <label className="grid">Роль <select className={field} name="role"><option value="support">Поддержка</option><option value="owner">Владелец</option></select></label>
          <button className={field} disabled={pending}>Отправить приглашение</button>
        </div>
        {message && <p role="status">{message}</p>}
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
