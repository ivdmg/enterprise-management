import { useLayoutEffect, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { BeamInput } from '@/components/FieldBeam';
import { companyAuth, CompanyRequestError, type LoginStep } from '@/api/companySession';
import { useAuth } from '@/context/AuthContext';
import { RecoveryCodes } from './RecoveryCodes';
import './AuthPage.css';

type Challenge = Exclude<LoginStep, { step: 'authenticated' }>;

export function CompanyAccessPage({ code }: { code: string }) {
  const { pathname, hash, search } = useLocation();
  const navigate = useNavigate();
  const { setCompanyProfile } = useAuth();
  const mode = pathname.endsWith('/invite') ? 'invite'
    : pathname.endsWith('/reset') ? 'reset'
      : pathname.endsWith('/forgot') ? 'forgot'
        : pathname.endsWith('/email-change') ? 'email-change' : 'login';
  const base = code ? `/c/${encodeURIComponent(code)}` : '';
  const [token] = useState(() => new URLSearchParams(hash.slice(1)).get('token')
    ?? new URLSearchParams(search).get('token') ?? '');
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [secret, setSecret] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [recovery, setRecovery] = useState<Extract<LoginStep, { step: 'authenticated' }> | null>(null);

  useLayoutEffect(() => {
    if (token && (hash || search) && ['invite', 'reset', 'email-change'].includes(mode)) {
      window.history.replaceState(window.history.state, '', pathname);
    }
  }, [hash, mode, pathname, search, token]);

  function finish(result: Extract<LoginStep, { step: 'authenticated' }>) {
    setCompanyProfile?.(result.profile);
    navigate(`/c/${encodeURIComponent(result.profile.company.code)}`, { replace: true });
  }

  async function acceptStep(result: LoginStep) {
    if (result.step === 'authenticated') {
      if (result.recovery_codes?.length) setRecovery(result);
      else finish(result);
      return;
    }
    if (result.step === 'mfa_enrollment_required') {
      const setup = await companyAuth.setupMfa(result.challenge_id);
      setSecret(setup.secret);
    }
    setChallenge(result);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const value = (name: string) => String(fields.get(name) ?? '');
    setError('');
    setPending(true);
    try {
      switch (mode) {
        case 'invite':
          await companyAuth.accept(token, value('password'), value('full_name').trim());
          setNotice('Приглашение принято. Теперь можно войти.');
          break;
        case 'reset':
          await companyAuth.reset(token, value('password'));
          setNotice('Пароль изменён. Войдите с новым паролем.');
          break;
        case 'email-change':
          await companyAuth.confirmEmail(token);
          setNotice('Адрес подтверждён. Теперь можно войти.');
          break;
        case 'forgot':
          await companyAuth.forgot((code || value('company_code')).trim(), value('email').trim());
          setNotice('Если адрес привязан к действующей учётной записи, мы отправим ссылку для восстановления.');
          break;
        case 'login':
          await acceptStep(challenge
            ? await companyAuth.verifyMfa(challenge.challenge_id, value('mfa_code').trim())
            : await companyAuth.login((code || value('company_code')).trim(), value('email').trim(), value('password')));
      }
    } catch (failure) {
      if (failure instanceof CompanyRequestError && failure.status === 429) {
        setError('Слишком много попыток. Попробуйте позже.');
      } else if (mode === 'login' && !challenge && failure instanceof CompanyRequestError && failure.status === 401) {
        setError('Проверьте код компании, почту и пароль.');
      } else if (mode === 'login' && challenge && failure instanceof CompanyRequestError && failure.status < 500) {
        setError('Не удалось подтвердить вход. Проверьте код или начните вход заново.');
      } else if (['invite', 'reset', 'email-change'].includes(mode) && failure instanceof CompanyRequestError && failure.status < 500) {
        setError('Не удалось использовать ссылку. Проверьте введённые данные или запросите новую ссылку.');
      } else {
        setError('Сервис временно недоступен. Попробуйте позже.');
      }
    } finally {
      setPending(false);
    }
  }

  if (recovery?.recovery_codes) return <RecoveryCodes codes={recovery.recovery_codes} onContinue={() => finish(recovery)} />;

  const titles = {
    login: challenge ? 'Подтвердите вход' : 'Вход в кабинет',
    invite: 'Принять приглашение',
    reset: 'Новый пароль',
    forgot: 'Восстановить доступ',
    'email-change': 'Подтвердить новый адрес',
  };
  const needsToken = ['invite', 'reset', 'email-change'].includes(mode);

  return (
    <main className="workspace-loading auth-page">
      <section className="auth-access" aria-labelledby="company-access-heading">
        <h1 id="company-access-heading">{titles[mode]}</h1>
        {notice ? <p role="status">{notice}</p> : needsToken && !token ? (
          <p role="alert">Ссылка недоступна. Запросите новую ссылку или обратитесь в поддержку.</p>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            {(mode === 'login' || mode === 'forgot') && !challenge && (
              <>
                {!code && <label>Код компании <BeamInput name="company_code" required /></label>}
                <label>Рабочая почта <BeamInput name="email" type="email" autoComplete="username" required /></label>
              </>
            )}
            {mode === 'invite' && <label>Имя и фамилия <BeamInput name="full_name" autoComplete="name" required /></label>}
            {(mode === 'invite' || mode === 'reset' || (mode === 'login' && !challenge)) && (
              <label>Пароль <BeamInput name="password" type="password" autoComplete={needsToken ? 'new-password' : 'current-password'} required /></label>
            )}
            {challenge && (
              <>
                {secret && <p>Введите ключ в приложение аутентификации <code>{secret}</code></p>}
                <label>Код подтверждения <BeamInput name="mfa_code" autoComplete="one-time-code" required /></label>
              </>
            )}
            {error && <p role="alert" className="auth-error">{error}</p>}
            <button className="auth-submit" disabled={pending}>{pending ? 'Отправляем…' : mode === 'login' ? 'Войти' : 'Продолжить'}</button>
          </form>
        )}
        {challenge ? (
          <button className="auth-switch" type="button" disabled={pending} onClick={() => { setChallenge(null); setSecret(''); setError(''); }}>
            Начать вход заново
          </button>
        ) : mode === 'login' ? (
          <a className="auth-switch" href={`${base}/forgot`}>Восстановить доступ</a>
        ) : <a className="auth-switch" href={`${base}/login`}>Перейти ко входу</a>}
      </section>
    </main>
  );
}
