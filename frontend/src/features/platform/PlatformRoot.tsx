import { useEffect, useLayoutEffect, useState, type FormEvent } from 'react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { RecoveryCodes } from '@/features/auth/RecoveryCodes';
import { BeamInput } from '@/components/FieldBeam';
import { platformAuth, PlatformRequestError, resetPlatformSession, type Operator, type OperatorLogin } from './platformApi';
import { PlatformCompanies, PlatformCompany, PlatformOwnerAudit } from './PlatformCompanies';
import { PlatformOperators } from './PlatformOperators';
import '@/features/auth/AuthPage.css';

export function PlatformRoot() {
  const [operator, setOperator] = useState<Operator | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    let active = true;
    const clear = () => { resetPlatformSession(); setOperator(null); };
    window.addEventListener('seh-platform-session-ended', clear);
    void platformAuth.profile()
      .then(value => { if (active) setOperator(value); })
      .catch(failure => {
        if (active && !(failure instanceof PlatformRequestError && failure.status === 401)
          && !(failure instanceof DOMException && failure.name === 'AbortError')) {
          setError('Не удалось проверить доступ к панели. Обновите страницу.');
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; window.removeEventListener('seh-platform-session-ended', clear); };
  }, []);

  function authenticated(value: Operator) {
    resetPlatformSession();
    setOperator(value);
    setError('');
    if (!pathname.startsWith('/platform/companies/')) navigate('/platform/companies', { replace: true });
  }

  async function logout() {
    try {
      await platformAuth.logout();
      resetPlatformSession();
      setOperator(null);
      navigate('/platform/login', { replace: true });
    } catch {
      setError('Не удалось завершить сессию. Попробуйте ещё раз.');
    }
  }

  if (pathname === '/platform/invite') return <OperatorAccess invite onLogin={authenticated} />;
  if (loading) return <main className="workspace-loading"><p role="status">Проверяем доступ к панели…</p></main>;
  if (!operator) return error ? <main className="workspace-loading"><p role="alert">{error}</p></main>
    : <OperatorAccess onLogin={authenticated} />;

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-5">
      <header className="flex flex-wrap items-center gap-4 border-b border-card-border pb-4">
        <strong>Панель платформы</strong>
        <Link className="underline" to="/platform/companies">Компании</Link>
        {operator.role === 'owner' && <Link className="underline" to="/platform/audit">Аудит</Link>}
        {operator.role === 'owner' && <Link className="underline" to="/platform/operators">Операторы</Link>}
        <span className="ml-auto">{operator.full_name}</span>
        <button className="rounded border border-card-border p-2" onClick={() => void logout()}>Выйти</button>
      </header>
      {error && <p role="alert">{error}</p>}
      <Routes>
        <Route path="/platform" element={<PlatformCompanies operator={operator} />} />
        <Route path="/platform/login" element={<PlatformCompanies operator={operator} />} />
        <Route path="/platform/companies" element={<PlatformCompanies operator={operator} />} />
        <Route path="/platform/companies/:id/*" element={<PlatformCompany operator={operator} />} />
        {operator.role === 'owner' && <Route path="/platform/audit" element={<PlatformOwnerAudit />} />}
        {operator.role === 'owner' && <Route path="/platform/operators" element={<PlatformOperators currentId={operator.id} />} />}
        <Route path="*" element={<p>Раздел недоступен.</p>} />
      </Routes>
    </main>
  );
}

function OperatorAccess({ invite = false, onLogin }: { invite?: boolean; onLogin: (value: Operator) => void }) {
  const { pathname, hash, search } = useLocation();
  const [token] = useState(() => new URLSearchParams(hash.slice(1)).get('token') ?? new URLSearchParams(search).get('token'));
  const [challenge, setChallenge] = useState<Exclude<OperatorLogin, { step: 'authenticated' }> | null>(null);
  const [secret, setSecret] = useState('');
  const [pending, setPending] = useState(false);
  const [recovery, setRecovery] = useState<Extract<OperatorLogin, { step: 'authenticated' }> | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState('');

  useLayoutEffect(() => {
    if (invite && token && (hash || search)) window.history.replaceState(window.history.state, '', pathname);
  }, [hash, invite, pathname, search, token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const read = (key: string) => String(fields.get(key) ?? '');
    setError('');
    setPending(true);
    try {
      if (invite && token) {
        await platformAuth.invite(token, read('full_name').trim(), read('password'));
        setAccepted(true);
        return;
      }
      const result = challenge
        ? await platformAuth.verify(challenge.challenge_id, read('code').trim())
        : await platformAuth.login(read('email').trim(), read('password'));
      if (result.step === 'authenticated') {
        if (result.recovery_codes?.length) setRecovery(result);
        else onLogin(result.profile);
      } else {
        if (result.step === 'mfa_enrollment_required') setSecret((await platformAuth.setup(result.challenge_id)).secret);
        setChallenge(result);
      }
    } catch (failure) {
      const status = failure instanceof PlatformRequestError ? failure.status : 500;
      setError(status === 429 ? 'Слишком много попыток. Попробуйте позже.'
        : status >= 500 || status === 404 && !invite ? 'Сервис временно недоступен.'
          : invite ? 'Не удалось принять приглашение. Проверьте ссылку или обратитесь к владельцу.'
            : challenge ? 'Не удалось подтвердить код. Проверьте его или начните вход заново.' : 'Проверьте почту и пароль.');
    } finally {
      setPending(false);
    }
  }

  if (recovery?.recovery_codes) return <RecoveryCodes codes={recovery.recovery_codes} onContinue={() => onLogin(recovery.profile)} />;

  return (
    <main className="workspace-loading auth-page">
      <section className="auth-access">
        <h1>{invite ? 'Приглашение в панель платформы' : challenge ? 'Подтверждение входа' : 'Вход в панель платформы'}</h1>
        {accepted ? <p role="status">Приглашение принято. <a className="underline" href="/platform/login">Перейти ко входу</a></p>
          : invite && !token ? <p role="alert">Ссылка недоступна. Обратитесь к владельцу панели.</p>
            : <form className="auth-form" onSubmit={submit}>
              {challenge ? <>
                {secret && <p>Введите ключ в приложение аутентификации <code>{secret}</code></p>}
                <label>Код <BeamInput name="code" autoComplete="one-time-code" required /></label>
              </> : <>
                {invite ? <label>Имя и фамилия <BeamInput name="full_name" autoComplete="name" required /></label>
                  : <label>Почта <BeamInput name="email" type="email" autoComplete="username" required /></label>}
                <label>Пароль <BeamInput name="password" type="password" autoComplete={invite ? 'new-password' : 'current-password'} required /></label>
              </>}
              {error && <p role="alert">{error}</p>}
              <button className="auth-submit" disabled={pending}>{pending ? 'Отправляем…' : 'Продолжить'}</button>
              {challenge && <button type="button" disabled={pending} onClick={() => { setChallenge(null); setSecret(''); setError(''); }}>Начать заново</button>}
            </form>}
      </section>
    </main>
  );
}
