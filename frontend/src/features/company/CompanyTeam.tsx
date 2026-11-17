import { useEffect, useState, type FormEvent } from 'react';
import { companyRequest, CompanyRequestError } from '@/api/companySession';
import { useAuth } from '@/context/AuthContext';

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  version: number;
}

interface AccessRequest {
  id: string;
  email: string;
  role: string;
  state: string;
}

const fieldClass = 'rounded-md border border-card-border bg-card px-2 py-1';
const accessStates = new Map([
  ['pending', 'На рассмотрении'], ['invited', 'Приглашение отправлено'],
  ['declined', 'Отклонена'], ['fulfilled', 'Доступ выдан'],
]);

export function CompanyTeam({ base }: { base: string }) {
  const { companyProfile } = useAuth();
  const [members, setMembers] = useState<TeamMember[] | null>(null);
  const [requests, setRequests] = useState<AccessRequest[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const canWrite = companyProfile?.permissions.includes('company.team.write');
  const canRequest = companyProfile?.permissions.includes('company.access.request');

  useEffect(() => {
    const controller = new AbortController();
    void companyRequest<TeamMember[]>('/company/users', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setMembers(value); })
      .catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить команду.'); });
    if (canRequest) {
      void companyRequest<AccessRequest[]>('/company/access-requests', { signal: controller.signal })
        .then(value => { if (!controller.signal.aborted) setRequests(value); })
        .catch(() => { if (!controller.signal.aborted) setError('Не удалось загрузить заявки.'); });
    }
    return () => controller.abort();
  }, [canRequest]);

  async function submit(event: FormEvent<HTMLFormElement>, member?: TeamMember) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const read = (key: string) => String(fields.get(key) ?? '').trim();
    const isActive = fields.has('active');
    if (member?.is_active && !isActive && !window.confirm('Отключить сотрудника и завершить его активные сессии?')) return;

    setError('');
    setNotice('');
    setPending(true);
    try {
      const role = read('role');
      const full_name = read('full_name');
      if (member) {
        const updated = await companyRequest<TeamMember>(`/company/users/${encodeURIComponent(member.id)}`, {
          method: 'PATCH',
          body: JSON.stringify({ version: member.version, full_name, role, is_active: isActive }),
        });
        setMembers(previous => previous?.map(item => item.id === updated.id ? updated : item) ?? []);
        setNotice('Данные сотрудника сохранены.');
      } else {
        const created = await companyRequest<AccessRequest>('/company/access-requests', {
          method: 'POST',
          body: JSON.stringify({ full_name, role, email: read('email'), reason: read('reason') || undefined }),
        });
        setRequests(previous => [created, ...(previous ?? [])]);
        form.reset();
        setNotice('Заявка отправлена в поддержку.');
      }
    } catch (failure) {
      setError(failure instanceof CompanyRequestError && failure.status === 409
        ? 'Данные изменились. Обновите страницу перед повторной отправкой.'
        : 'Не удалось сохранить изменения.');
    } finally {
      setPending(false);
    }
  }

  async function requestEmailChange(event: FormEvent<HTMLFormElement>, member: TeamMember) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const newEmail = String(fields.get('new_email') ?? '').trim();
    setError('');
    setNotice('');
    setPending(true);
    try {
      await companyRequest(`/company/users/${encodeURIComponent(member.id)}/email-change`, {
        method: 'POST',
        body: JSON.stringify({ version: member.version, new_email: newEmail, password: fields.get('password') }),
      });
      form.reset();
      setNotice('Отправлен запрос на подтверждение нового адреса.');
    } catch (failure) {
      setError(failure instanceof CompanyRequestError && failure.status === 409
        ? 'Данные изменились. Обновите страницу.'
        : 'Не удалось запросить смену адреса.');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-5">
      <a className="underline" href={base}>Вернуться в кабинет</a>
      <h1 className="text-xl font-semibold">Команда компании</h1>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!members ? !error && <p role="status">Загрузка команды…</p> : (
        members.length ? <ul className="space-y-3">{members.map(member => (
          <li key={member.id} className="space-y-2 rounded-lg border border-card-border bg-card p-4">
            <p>{member.full_name} · {member.email}</p>
            <p>{member.is_active ? 'Доступ активен' : 'Доступ отключён'}</p>
            {canWrite && ['manager', 'viewer'].includes(member.role) && (
              <form key={member.version} className="flex flex-wrap items-end gap-3" onSubmit={event => void submit(event, member)}>
                <label className="grid gap-1">Имя <input className={fieldClass} name="full_name" defaultValue={member.full_name} required /></label>
                <label className="grid gap-1">Доступ <RoleSelect initial={member.role} /></label>
                <label><input name="active" type="checkbox" defaultChecked={member.is_active} /> Активен</label>
                <button className={fieldClass} disabled={pending}>Сохранить</button>
                            </form>
            )}
            {canWrite && ['manager', 'viewer'].includes(member.role) && (
              <form className="flex flex-wrap items-end gap-3" onSubmit={event => void requestEmailChange(event, member)}>
                <label className="grid gap-1">Новая почта <input className={fieldClass} name="new_email" type="email" required /></label>
                <label className="grid gap-1">Ваш пароль <input className={fieldClass} name="password" type="password" autoComplete="current-password" required /></label>
                <button className={fieldClass} disabled={pending}>Запросить смену</button>
              </form>
            )}
          </li>
        ))}</ul> : <p>Сотрудников пока нет.</p>
      )}
      {canRequest && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Запросить доступ для сотрудника</h2>
          <form className="grid max-w-xl gap-3" onSubmit={event => void submit(event)}>
            <label className="grid gap-1">Имя <input className={fieldClass} name="full_name" required /></label>
            <label className="grid gap-1">Рабочая почта <input className={fieldClass} type="email" name="email" required /></label>
            <label className="grid gap-1">Доступ <RoleSelect initial="viewer" /></label>
            <label className="grid gap-1">Комментарий <input className={fieldClass} name="reason" /></label>
            <button className={fieldClass} disabled={pending}>Отправить заявку</button>
          </form>
          {requests?.length ? <ul>{requests.map(item => (
            <li key={item.id}>{item.email} · {accessStates.get(item.state) ?? 'Статус неизвестен'}</li>
          ))}</ul> : requests && <p>Заявок пока нет.</p>}
        </section>
      )}
    </main>
  );
}

function RoleSelect({ initial }: { initial: string }) {
  return (
    <select className={fieldClass} name="role" defaultValue={initial}>
      <option value="viewer">Просмотр</option>
      <option value="manager">Просмотр и изменения</option>
    </select>
  );
}
