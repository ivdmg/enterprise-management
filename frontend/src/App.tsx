import { FieldBeam } from '@/components/FieldBeam';
import { Activity, Bell, Building2, Database, FileStack, LayoutDashboard, ListChecks, LogOut, Moon, PanelLeftOpen, Settings, Sun, Truck, Wallet, Workflow, Package, Search, FlaskConical, House, ChevronRight, ChevronDown } from 'lucide-react';
import { lazy, Suspense, useEffect, useState, type CSSProperties } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { AuthPage } from '@/features/auth/AuthPage';
import { CustomerTendersTab, type TenderView } from '@/features/dashboard/CustomerTendersTab';
import { ProjectsTab } from '@/features/dashboard/ProjectsTab';
import { ProcurementTab } from '@/features/procurement/ProcurementTab';
import { DispatchTab } from '@/features/dispatch/DispatchTab';
import { TasksTab } from '@/features/tasks/TasksTab';
import { FilesTab } from '@/features/files/FilesTab';
import { SettingsTab } from '@/features/settings/SettingsTab';
import { FileUploadModal } from '@/features/files/FileUploadModal';
import { AccountantUploadModal } from '@/features/files/AccountantUploadModal';
import { MappingDrawer } from '@/features/files/MappingDrawer';
import { AlertsDrawer, isContractPenalty } from '@/features/alerts/AlertsDrawer';
import { apiClient } from '@/api/client';
import { demoMode } from '@/api/mode';
import { Modal } from '@/components/Modal';
import type { DriveSyncStatus } from '@/types';
import './workspace.css';

const sections = [
  { title: 'Контроль', items: [
    { id: 'summary', label: 'Где горит?', icon: LayoutDashboard, description: 'Сроки и обязательства, которые стоит проверить в первую очередь.' },
    { id: 'registry', label: 'Контракты', icon: FileStack, description: 'Заказчики, статусы и сроки из реестра.' },
    { id: 'monitoring', label: 'Документы и сроки', icon: Activity, description: 'Контроль исполнения и отметок о документах.' },
  ] },
  { title: 'Операции', items: [
    { id: 'projects', label: 'Тендеры и объекты', icon: Building2, description: 'Этапы контрактов и сроки банковских гарантий.' },
    { id: 'finance', label: 'Финансы', icon: Wallet, description: 'Движение денег, поступления и расходы.' },
    { id: 'procurement', label: 'Снабжение и закупки', icon: Package, description: 'Счета, материалы и движение поставок.' },
    { id: 'dispatch', label: 'Диспетчерская', icon: Truck, description: 'Состояние техники и журнал происшествий.' },
    { id: 'tasks', label: 'Смарт-реестр задач', icon: ListChecks, description: 'Поручения, сроки и ответственные по объектам.' },
  ] },
  { title: 'Данные', items: [
    { id: 'sources', label: 'Источники данных', icon: Database, description: 'Подключённые листы и качество импорта.' },
    { id: 'files', label: 'Файлы и интеграция', icon: FileStack, description: 'Файлы компании, импорт и передача отчётов.' },
    { id: 'settings', label: 'Настройки', icon: Settings, description: 'Профиль компании и настройки интеграций.' },
  ] },
] as const;

type Section = typeof sections[number]['items'][number]['id'];
const customerViews: readonly Section[] = ['summary', 'registry', 'monitoring', 'sources'];
const QuickActions = lazy(() => import('@/components/QuickActions'));
const FinanceTab = lazy(() => import('@/features/dashboard/FinanceTab').then(module => ({ default: module.FinanceTab })));
const formatSync = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Astrakhan' });

function readSection(): Section {
  const hash = window.location.hash.slice(1).split('?')[0];
  return sections.flatMap(group => [...group.items]).find(item => item.id === hash)?.id ?? 'summary';
}

export default function App() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [view, setView] = useState(readSection);
  const [procurementDue, setProcurementDue] = useState(() => window.location.hash === '#procurement?due');
  const [sidebar, setSidebar] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [sync, setSync] = useState<DriveSyncStatus | null>(null);
  const [showAlerts, setShowAlerts] = useState<'all' | 'penalties' | null>(null);
  const [penalties, setPenalties] = useState<number | null>(null);
  const [upload, setUpload] = useState<'file' | 'accounting' | null>(null);
  const [mapping, setMapping] = useState<{ id: string; name: string } | null>(null);
  const [version, setVersion] = useState(0);
  const canEdit = user?.role === 'admin' || user?.role === 'manager';
  const section = sections.flatMap(group => [...group.items]).find(item => item.id === view)!;

  useEffect(() => {
    const onHashChange = () => {
      setView(readSection());
      setProcurementDue(window.location.hash === '#procurement?due');
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    const refresh = () => apiClient.getDriveSyncStatus().then(data => { if (active) setSync(data); }).catch(() => {});
    apiClient.getAlerts().then(data => {
      const amounts = data.filter(isContractPenalty);
      if (active) setPenalties(amounts.length ? amounts.reduce((total, alert) => total + alert.calculated_financial_impact, 0) : null);
    }).catch(() => { if (active) setPenalties(null); });
    refresh();
    const timer = window.setInterval(refresh, 60_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [isAuthenticated, showAlerts]);

  useEffect(() => {
    const openSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        if (isAuthenticated) setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', openSearch);
    return () => window.removeEventListener('keydown', openSearch);
  }, [isAuthenticated]);

  useEffect(() => {
    if (!sidebar) return;
    const root = document.documentElement;
    const previousOverflow = root.style.overflow;
    root.style.overflow = 'hidden';
    document.querySelector<HTMLButtonElement>('.workspace-sidebar-head button')?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebar(false);
        document.getElementById('workspace-menu-toggle')?.focus();
      }
    };
    window.addEventListener('keydown', close);
    return () => {
      root.style.overflow = previousOverflow;
      window.removeEventListener('keydown', close);
    };
  }, [sidebar]);

  function navigate(next: Section, due = false) {
    const hash = next === 'procurement' && due ? 'procurement?due' : next;
    if (window.location.hash !== `#${hash}`) {
      window.location.hash = hash;
      setView(next);
      setProcurementDue(due);
      window.scrollTo(0, 0);
    }
    setSidebar(false);
  }

  if (isLoading) return <main className="workspace-loading" role="status">Открываем рабочее пространство…</main>;
  if (!isAuthenticated) return <AuthPage />;

  const lastSync = Date.parse(sync?.last_synced_at ?? '');
  const syncLabel = sync?.status === 'syncing' ? 'Идёт импорт' : sync?.status === 'error' ? 'Ошибка импорта' : Number.isFinite(lastSync) ? formatSync.format(lastSync) : 'Google Drive';
  const customerView = customerViews.includes(view);

  function renderSection() {
    switch (view) {
      case 'projects': return <ProjectsTab />;
      case 'finance': return <FinanceTab />;
      case 'procurement': return <ProcurementTab key={String(procurementDue)} dueOnly={procurementDue} />;
      case 'dispatch': return <DispatchTab />;
      case 'tasks': return <TasksTab />;
      case 'files': return <FilesTab readOnly={!canEdit} onUploadClick={() => setUpload('file')} onAccountantUploadClick={canEdit ? () => setUpload('accounting') : undefined} onFileSelect={(id, name) => setMapping({ id, name })} />;
      case 'settings': return <SettingsTab />;
      default: return null;
    }
  }

  return (
    <div className="workspace" data-sidebar={sidebar ? 'open' : 'closed'}>
      <header className="workspace-topbar" inert={sidebar}>
        <div className="workspace-topbar-strip"><div className="workspace-topbar-start">
          <a href="#summary" className="workspace-brand" aria-label="Enterprise Hub — обзор" onClick={event => { event.preventDefault(); navigate('summary'); }}>
            <span className="workspace-brand-mark"><Workflow size={18} />

            </span><strong>Enterprise Hub</strong>
          </a>
          <span className="workspace-current"><ChevronRight size={13} />{section.label}</span>
        </div>
        <div className="workspace-topbar-actions">
          {demoMode && <span className="workspace-demo" title="Учебные данные"><FlaskConical size={14} />Демо</span>}
          {!demoMode && <button className="workspace-sync" onClick={() => navigate('sources')} title={`Состояние Google Drive: ${syncLabel}`} aria-label={`Состояние Google Drive: ${syncLabel}`}><Database size={15} /><span>{syncLabel}</span></button>}
          <button className="workspace-icon-button" onClick={() => setShowAlerts('all')} title="Уведомления" aria-label="Уведомления"><Bell size={18} /></button>
          <button className="workspace-icon-button" onClick={toggle} title={isDark ? 'Светлая тема' : 'Тёмная тема'} aria-label={isDark ? 'Светлая тема' : 'Тёмная тема'}>{isDark ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="workspace-profile-trigger" type="button" popoverTarget="workspace-profile" aria-label="Меню профиля" title="Меню профиля">{user?.full_name?.trim().charAt(0) || 'Р'}</button>
          <div id="workspace-profile" popover="auto" className="workspace-profile">
            <div className="workspace-profile-account"><strong>{user?.full_name || 'Руководитель'}</strong><small>{user?.email}</small></div>
            <button type="button" popoverTarget="workspace-profile" popoverTargetAction="hide" onClick={() => navigate('settings')}><Settings size={16} />Настройки профиля</button>
            <button type="button" onClick={() => { setSync(null); setPenalties(null); setShowAlerts(null); setUpload(null); setMapping(null); navigate('summary'); logout(); }}><LogOut size={16} />Выйти</button>
          </div>
        </div>
        </div>
        <nav className="workspace-tabs" aria-label="Быстрый доступ к разделам"><div className="workspace-tabs-title"><button id="workspace-menu-toggle" type="button" className="workspace-icon-button" aria-controls="workspace-sidebar" aria-expanded={sidebar} aria-label={sidebar ? 'Свернуть разделы' : 'Развернуть разделы'} onClick={() => setSidebar(open => !open)}><PanelLeftOpen size={19} /></button><strong>Панель руководителя</strong></div>
          {[
            { label: 'Обзор', ids: ['summary'] },
            { label: 'Контракты', ids: ['registry', 'projects', 'monitoring'] },
            { label: 'Финансы', ids: ['finance'] },
            { label: 'Операции', ids: ['procurement', 'dispatch', 'tasks'] },
            { label: 'Данные', ids: ['sources', 'files', 'settings'] },
          ].map(({ label, ids }, index) => {
            const items = sections.flatMap(group => [...group.items]).filter(item => ids.includes(item.id));
            const active = ids.includes(view);
            if (items.length === 1) {
              const { id } = items[0];
              return <a key={label} href={`#${id}`} aria-current={active ? 'page' : undefined} onClick={event => { if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; event.preventDefault(); navigate(id); }}>{label}</a>;
            }
            const menuId = `workspace-nav-${index}`;
            const anchor = `--${menuId}`;
            return <div key={label} className="workspace-nav-popover">
              <button type="button" className="workspace-nav-trigger" data-active={active} popoverTarget={menuId} style={{ anchorName: anchor } as CSSProperties}>{label}<ChevronDown size={13} /></button>
              <div id={menuId} popover="auto" className="workspace-nav-menu" style={{ positionAnchor: anchor } as CSSProperties}>
                {items.map(({ id, label, icon: Icon }) =>
                  <button key={id} type="button" aria-current={view === id ? 'page' : undefined} popoverTarget={menuId} popoverTargetAction="hide" onClick={() => navigate(id)}><Icon size={16} />{label}</button>,
                )}
              </div>
            </div>;
          })}
          {(canEdit || sync?.root_folder_link) && <Suspense fallback={null}><QuickActions
            onUpload={canEdit ? () => setUpload('file') : undefined}
            onAccounting={canEdit ? () => setUpload('accounting') : undefined}
            driveLink={demoMode ? undefined : sync?.root_folder_link}
          /></Suspense>}
        </nav>
      </header>
      {sidebar && <button type="button" className="workspace-scrim" aria-label="Закрыть разделы" onClick={() => { setSidebar(false); document.getElementById('workspace-menu-toggle')?.focus(); }} />}
      <aside id="workspace-sidebar" className="workspace-sidebar" aria-label="Навигация"><div className="workspace-sidebar-head"><span className="workspace-brand"><span><Workflow size={18} /></span><strong>Enterprise Hub</strong></span><button type="button" className="workspace-icon-button" aria-label="Закрыть меню" onClick={() => { setSidebar(false); requestAnimationFrame(() => document.getElementById('workspace-menu-toggle')?.focus()); }}>×</button></div>
        <nav aria-label="Разделы">
          {sections.map(group => <div className="workspace-nav-group" key={group.title}>
            <p>{group.title}</p>
            {group.items.map(({ id, label, icon: Icon }) => <a key={id} href={`#${id}`} aria-label={label} title={label} aria-current={view === id ? 'page' : undefined} onClick={event => { if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; event.preventDefault(); navigate(id); }}><Icon size={18} /><span>{label}</span></a>)}
          </div>)}
        </nav>
      </aside>
      <main className="workspace-main" data-view={view} inert={sidebar}>
        {customerView ? <CustomerTendersTab view={view as TenderView} onViewChange={navigate} penalties={penalties} onOpenAlerts={() => setShowAlerts('penalties')} onOpenProcurement={() => navigate('procurement', true)} onOpenFinance={() => navigate('finance')} />
          : <>
              {view !== 'finance' && <header className="workspace-heading workspace-pagebar"><div><div className="workspace-eyebrow"><section.icon size={15} /> ENTERPRISE HUB</div><h1>{section.label}</h1><p>{section.description}</p></div><button type="button" className="workspace-icon-button workspace-home-button" aria-label="К обзору" title="К обзору" onClick={() => navigate('summary')}><House size={17} /></button></header>}
              <div key={`${view}-${version}`} className="workspace-module workspace-reveal"><Suspense fallback={<p role="status">Загружаем раздел…</p>}>{renderSection()}</Suspense></div>
            </>}
      </main>
      <FileUploadModal isOpen={canEdit && upload === 'file'} onClose={() => setUpload(null)} onUploadComplete={data => { setUpload(null); if (data.status === 'awaiting_confirmation') setMapping({ id: data.file_id, name: data.original_name }); setVersion(value => value + 1); }} />
      <AccountantUploadModal isOpen={canEdit && upload === 'accounting'} onClose={() => setUpload(null)} onUploadSuccess={() => { setUpload(null); setVersion(value => value + 1); navigate('tasks'); }} />
      <MappingDrawer isOpen={canEdit && mapping !== null} onClose={() => { setMapping(null); setVersion(value => value + 1); }} fileId={mapping?.id ?? ''} fileName={mapping?.name ?? ''} />
      {searchOpen && <Modal isOpen title="Быстрый переход" onClose={() => { setSearchOpen(false); setQuery(''); }}>
        <div className="workspace-search-dialog">
          <FieldBeam className="workspace-search-beam"><label className="workspace-search"><Search size={18} /><input autoFocus aria-label="Поиск по разделам" placeholder="Например, финансы" value={query} onChange={event => setQuery(event.target.value)} /></label></FieldBeam>
          <div className="workspace-search-results">
            {sections.flatMap(group => [...group.items]).filter(item => (item.label + ' ' + item.description).toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))).map(({ id, label, icon: Icon }) =>
              <button key={id} onClick={() => { navigate(id); setSearchOpen(false); setQuery(''); }}><Icon size={17} />{label}<ChevronRight size={15} /></button>,
            )}
          </div>
        </div>
      </Modal>}
      <AlertsDrawer isOpen={showAlerts !== null} penaltiesOnly={showAlerts === 'penalties'} onClose={() => setShowAlerts(null)} />
    </div>
  );
}
