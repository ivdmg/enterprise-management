import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { companyClientEnabled, companyRequest } from '@/api/companySession';
import { useAuth } from '@/context/AuthContext';
import App from '@/App';
import { CompanyAccessPage } from '@/features/auth/CompanyAccessPage';
import { CompanyAudit } from './CompanyAudit';
import { CompanyTeam } from './CompanyTeam';

export interface CompanyModule {
  id: string;
  label: string;
  order: number;
  permissions: string[];
}

export function ClientRoot() {
  return companyClientEnabled ? <CompanyRoot /> : <App />;
}

function CompanyRoot() {
  const { companyProfile, isLoading, bootstrapError, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [, code = '', page = '', module] = /^\/c\/([a-zA-Z0-9_-]+)(?:\/([^/]+))?(?:\/([^/]+))?\/?$/.exec(pathname) ?? [];
  const [logoutError, setLogoutError] = useState(false);
  const accessLink = ['invite', 'reset', 'email-change'].includes(page);

  useEffect(() => {
    if (companyProfile && !code) {
      navigate(`/c/${encodeURIComponent(companyProfile.company.code)}`, { replace: true });
    }
  }, [companyProfile, code, navigate]);

  if (accessLink) return <CompanyAccessPage key={pathname} code={code} />;
  if (isLoading) return <main className="workspace-loading"><p role="status">Проверяем доступ…</p></main>;
  if (bootstrapError && !companyProfile) return <main className="workspace-loading"><p role="alert">Не удалось проверить доступ. Обновите страницу.</p></main>;
  if (!companyProfile) return <CompanyAccessPage key={pathname} code={code} />;

  const base = `/c/${encodeURIComponent(companyProfile.company.code)}`;
  if (code !== companyProfile.company.code) return (
    <main className="workspace-loading">
      <section className="space-y-3">
        <p>Этот кабинет недоступен в текущей сессии.</p>
        <a className="block underline" href={base}>Открыть свой кабинет</a>
        <button type="button" onClick={async () => {
          setLogoutError(false);
          try { await logout(); } catch { setLogoutError(true); }
        }}>Выйти для смены компании</button>
        {logoutError && <p role="alert">Не удалось завершить сессию. Попробуйте ещё раз.</p>}
      </section>
    </main>
  );
  return <CompanyWorkspace key={companyProfile.id + ':' + companyProfile.company.id} base={base} page={page} module={module} />;
}

function CompanyWorkspace({ base, page, module }: { base: string; page: string; module?: string }) {
  const { companyProfile } = useAuth();
  const [modules, setModules] = useState<CompanyModule[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (page === 'team' || page === 'audit') return;
    const controller = new AbortController();
    void companyRequest<{ modules: CompanyModule[] }>('/company/modules', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setModules(data.modules); setError(false); } })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [page]);

  if (page === 'team' && companyProfile?.permissions.includes('company.team.read')) return <CompanyTeam base={base} />;
  if (page === 'audit' && companyProfile?.permissions.includes('company.audit.read')) return <CompanyAudit base={base} />;
  if (!['', 'login', 'm'].includes(page) || (page === 'm' && !module)) return (
    <main className="workspace-loading"><p>Раздел недоступен. <a className="underline" href={base}>В кабинет</a></p></main>
  );
  if (error) return <main className="workspace-loading"><p role="alert">Не удалось загрузить разделы. Обновите страницу.</p></main>;
  if (!modules) return <main className="workspace-loading"><p role="status">Загружаем разделы…</p></main>;
  return <App allowedModules={modules} companyBase={base} requestedModule={module} />;
}
