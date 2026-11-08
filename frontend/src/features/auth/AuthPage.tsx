import { BeamInput } from '@/components/FieldBeam';
import { ArrowRight, CalendarDays, Files, Workflow } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { demoMode } from '@/api/mode';
import './AuthPage.css';

const registrationEnabled = !demoMode && import.meta.env.VITE_ALLOW_REGISTRATION === 'true';

export function AuthPage() {
  const { login, register } = useAuth();
  const [registering, setRegistering] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const email = String(fields.get('email') ?? '').trim();
    const password = String(fields.get('password') ?? '');
    setError('');
    setPending(true);
    try {
      if (registering) {
        await register({
          company_name: String(fields.get('company_name') ?? '').trim(),
          full_name: String(fields.get('full_name') ?? '').trim(),
          email,
          password,
        });
      } else {
        await login(email, password);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : registering ? 'Не удалось создать компанию.' : 'Не удалось войти.');
    } finally {
      setPending(false);
    }
  }

  const heading = demoMode ? 'Демонстрационное пространство' : registering ? 'Создайте компанию' : 'Вход в систему';
  const action = demoMode ? 'Открыть демо' : registering ? 'Создать компанию' : 'Войти';

  return (
    <main className="workspace-loading auth-page">
      <div className="auth-layout">
        <section className="auth-intro" aria-label="Enterprise Hub">
          <div className="auth-brand"><Workflow size={22} aria-hidden="true" /> Enterprise Hub</div>
          <div>
            <p className="auth-kicker">Панель руководителя</p>
            <h2>Управляйте сроками и контрактами</h2>
          </div>
          <ul className="auth-features">
            <li><CalendarDays size={18} aria-hidden="true" /> Контроль сроков</li>
            <li><Files size={18} aria-hidden="true" /> Документы и контракты</li>
          </ul>
        </section>

        <section className="auth-access" aria-labelledby="auth-heading">
          <p className="auth-kicker">Рабочее пространство</p>
          <h1 id="auth-heading">{heading}</h1>
          <p>{demoMode ? 'Посмотрите, как устроены разделы, на учебных данных.' : registering ? 'Укажите название компании и данные администратора.' : 'Введите данные вашей учётной записи.'}</p>
          <form key={String(registering)} className="auth-form" onSubmit={submit}>
            {registering && <>
              <label>Название компании
                <BeamInput name="company_name" autoComplete="organization" minLength={2} maxLength={255} required />
              </label>
              <label>Имя и фамилия
                <BeamInput name="full_name" autoComplete="name" minLength={2} maxLength={255} required />
              </label>
            </>}
            {!demoMode && <>
              <label>Рабочая почта
                <BeamInput name="email" type="email" autoComplete="username" required />
              </label>
              <label>Пароль
                <BeamInput name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 8 : undefined} required />
                {registering && <small>Минимум 8 символов</small>}
              </label>
            </>}
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" disabled={pending}>
              {pending ? (registering ? 'Создаём компанию…' : 'Входим…') : action}
              <ArrowRight size={19} aria-hidden="true" />
            </button>
          </form>
          {registrationEnabled && (
            <button className="auth-switch" type="button" disabled={pending} onClick={() => {
              setError('');
              setRegistering(!registering);
            }}>
              {registering ? 'Уже есть учётная запись? Войти' : 'Создать компанию'}
            </button>
          )}
        </section>
      </div>
    </main>
  );
}
