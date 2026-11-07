import { Workflow } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useAuth } from '@/context/AuthContext';

export function AuthPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      await login(email.trim(), password);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось войти.');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="workspace-loading px-5">
      <div className="w-full max-w-md">
        <div className="workspace-hero rounded-b-none">
          <div className="workspace-eyebrow"><Workflow size={16} /> ENTERPRISE HUB</div>
          <h2>Панель руководителя</h2>
          <p>Контракты, документы и сроки в одной сводке.</p>
        </div>
        <form className="workspace-panel rounded-t-none space-y-4" onSubmit={submit}>
          <h1 className="text-xl font-bold">Вход в рабочее пространство</h1>
          {error && <p className="workspace-badge late" role="alert">{error}</p>}
          <label className="block text-sm font-medium">Почта
            <input className="mt-1 block w-full rounded-lg border border-[var(--card-border)] p-3" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required />
          </label>
          <label className="block text-sm font-medium">Пароль
            <input className="mt-1 block w-full rounded-lg border border-[var(--card-border)] p-3" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
          </label>
          <button className="w-full rounded-lg workspace-auth-submit px-4 py-3 font-semibold disabled:opacity-60" disabled={pending}>{pending ? 'Входим…' : 'Войти'}</button>
        </form>
      </div>
    </main>
  );
}
