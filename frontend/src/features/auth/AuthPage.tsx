import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { Button } from '@/components/Button';
import { BarChart3, Moon, Sun } from 'lucide-react';

export function AuthPage() {
  const { login, register } = useAuth();
  const { isDark, toggle } = useTheme();
  const [isLogin, setIsLogin] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [inn, setInn] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register({ company_name: companyName, inn: inn || undefined, full_name: fullName, email, password });
      }
    } catch (err: any) {
      setError(err.message || 'Произошла ошибка');
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass =
    'w-full px-3 py-2 text-sm rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-colors';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col">
      {/* Top bar with theme toggle */}
      <div className="flex justify-end p-4">
        <button
          onClick={toggle}
          className="p-2 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
          aria-label="Переключить тему"
        >
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="flex items-center justify-center gap-2.5 mb-8">
            <div className="p-2 rounded-lg bg-indigo-600">
              <BarChart3 className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Smart Enterprise Hub
            </span>
          </div>

          {/* Form Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6">
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">
              {isLogin ? 'Вход в систему' : 'Регистрация компании'}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">
              {isLogin
                ? 'Введите данные для доступа к платформе'
                : 'Создайте аккаунт для вашей компании'}
            </p>

            {error && (
              <div className="mb-4 px-3 py-2 rounded-md bg-rose-500/10 border border-rose-500/20 text-sm text-rose-600 dark:text-rose-400">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <>
                  <div>
                    <label htmlFor="auth-company" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Название компании
                    </label>
                    <input
                      id="auth-company"
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="ООО ГлавСтрой"
                      required
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label htmlFor="auth-inn" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      ИНН (необязательно)
                    </label>
                    <input
                      id="auth-inn"
                      type="text"
                      value={inn}
                      onChange={(e) => setInn(e.target.value)}
                      placeholder="7701234567"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label htmlFor="auth-name" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      ФИО
                    </label>
                    <input
                      id="auth-name"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Иванов Иван Иванович"
                      required
                      className={inputClass}
                    />
                  </div>
                </>
              )}
              <div>
                <label htmlFor="auth-email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Email
                </label>
                <input
                  id="auth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="director@company.ru"
                  required
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="auth-password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Пароль
                </label>
                <input
                  id="auth-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Минимум 8 символов"
                  required
                  minLength={8}
                  className={inputClass}
                />
              </div>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading
                  ? 'Загрузка...'
                  : isLogin
                  ? 'Войти'
                  : 'Зарегистрировать'}
              </Button>
            </form>

            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                }}
                className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                {isLogin ? 'Нет аккаунта? Зарегистрируйтесь' : 'Уже есть аккаунт? Войти'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
