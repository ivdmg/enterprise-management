import { DataLoading } from '@/components/DataLoading';
import { FieldBeam } from '@/components/FieldBeam';
import { Bell, Building2, Database, FileStack, LayoutDashboard, ListChecks, LoaderCircle, LogOut, Moon, PanelLeftClose, PanelLeftOpen, Settings, Sun, Truck, Wallet, Workflow, Package, Search, FlaskConical, House, ChevronRight, ChevronDown, ExternalLink, Upload, UserRound } from 'lucide-react';
import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { AuthPage } from '@/features/auth/AuthPage';
import { CustomerTendersTab, type TenderView } from '@/features/dashboard/CustomerTendersTab';
import { FileUploadModal } from '@/features/files/FileUploadModal';
import { AccountantUploadModal } from '@/features/files/AccountantUploadModal';
import { MappingDrawer } from '@/features/files/MappingDrawer';
import { AlertsDrawer, isContractPenalty } from '@/features/alerts/AlertsDrawer';
import { apiClient, clearSectionData } from '@/api/client';
import { demoMode } from '@/api/mode';
import { Modal } from '@/components/Modal';
import type { DriveSyncStatus } from '@/types';
import './workspace.css';

const sections = [
  { title: 'Контроль', items: [
    { id: 'summary', label: 'Где горит?', icon: LayoutDashboard, description: 'Сроки и обязательства, которые стоит проверить в первую очередь.' },
    { id: 'registry', label: 'Контракты', icon: FileStack, description: 'Реестр контрактов, сроки исполнения и контроль документов.' },
    { id: 'engineers', label: 'Документы инженеров', icon: UserRound, description: 'Удостоверения, отметки в реестре и даты, требующие проверки.' },
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
const customerViews: readonly Section[] = ['summary', 'registry', 'sources'];
const QuickActions = lazy(() => import('@/components/QuickActions'));
const loadSection = {
  engineers: () => import('@/features/dashboard/EngineerDocumentsTab').then(module => ({ default: module.EngineerDocumentsTab })),
  projects: () => import('@/features/dashboard/ProjectsTab').then(module => ({ default: module.ProjectsTab })),
  finance: () => import('@/features/dashboard/FinanceTab').then(module => ({ default: module.FinanceTab })),
  procurement: () => import('@/features/procurement/ProcurementTab').then(module => ({ default: module.ProcurementTab })),
  dispatch: () => import('@/features/dispatch/DispatchTab').then(module => ({ default: module.DispatchTab })),
  tasks: () => import('@/features/tasks/TasksTab').then(module => ({ default: module.TasksTab })),
  files: () => import('@/features/files/FilesTab').then(module => ({ default: module.FilesTab })),
  settings: () => import('@/features/settings/SettingsTab').then(module => ({ default: module.SettingsTab })),
};
const EngineerDocumentsTab = lazy(loadSection.engineers);
const ProjectsTab = lazy(loadSection.projects);
const FinanceTab = lazy(loadSection.finance);
const ProcurementTab = lazy(loadSection.procurement);
const DispatchTab = lazy(loadSection.dispatch);
const TasksTab = lazy(loadSection.tasks);
const FilesTab = lazy(loadSection.files);
const SettingsTab = lazy(loadSection.settings);
const prefetchOrder: readonly Section[] = ['registry', 'finance', 'engineers', 'summary', 'projects', 'procurement', 'dispatch', 'tasks', 'sources', 'files', 'settings'];

function prefetchSection(view: Section, canEdit: boolean, showDrive: boolean) {
  switch (view) {
    case 'summary': return Promise.allSettled([apiClient.getCustomerTenders(), apiClient.getFinanceData('month')]);
    case 'registry': return Promise.allSettled([apiClient.getCustomerTenders()]);
    case 'sources': return Promise.allSettled([
      apiClient.getCustomerTenders(),
      ...(canEdit && !demoMode ? [apiClient.getDriveCatalog(), apiClient.getEngineerDocuments()] : []),
    ]);
    case 'engineers': return Promise.allSettled(canEdit && !demoMode ? [loadSection.engineers(), apiClient.getEngineerDocuments()] : []);
    case 'projects': return Promise.allSettled([loadSection.projects(), apiClient.getProjects()]);
    case 'finance': return Promise.allSettled([loadSection.finance(), apiClient.getFinanceData('month')]);
    case 'procurement': return Promise.allSettled([loadSection.procurement(), apiClient.getProcurementItems()]);
    case 'dispatch': return Promise.allSettled([loadSection.dispatch(), apiClient.getDispatchRecords()]);
    case 'tasks': return Promise.allSettled([loadSection.tasks(), apiClient.getTasks()]);
    case 'files': return Promise.allSettled([loadSection.files(), apiClient.getFiles(), ...(showDrive ? [apiClient.getDriveCatalog()] : [])]);
    case 'settings': return Promise.allSettled([loadSection.settings(), apiClient.getTelegramSettings()]);
  }
}
const formatSync = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Astrakhan' });

function readSection(): Section {
  const hash = window.location.hash.slice(1).split('?')[0];
  if (hash === 'monitoring') return 'registry';
  return sections.flatMap(group => [...group.items]).find(item => item.id === hash)?.id ?? 'summary';
}

export default function App() {
  const { user, tokens, isAuthenticated, isLoading, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [view, setView] = useState(readSection);
  const [procurementDue, setProcurementDue] = useState(() => window.location.hash === '#procurement?due');
  const [sidebar, setSidebar] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [manualSync, setManualSync] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [sync, setSync] = useState<DriveSyncStatus | null>(null);
  const [showAlerts, setShowAlerts] = useState<'all' | 'penalties' | null>(null);
  const [penalties, setPenalties] = useState<number | null>(null);
  const [upload, setUpload] = useState<'file' | 'accounting' | null>(null);
  const [mapping, setMapping] = useState<{ id: string; name: string } | null>(null);
  const [version, setVersion] = useState(0);
  const canEdit = user?.role === 'admin' || user?.role === 'manager';
  const showDrive = canEdit && !demoMode && sync?.drive_mode !== 'mock';
  const currentView = useRef(view);
  const currentToken = useRef(tokens?.access_token);
  const prefetchRun = useRef<AbortController | null>(null);
  const section = sections.flatMap(group => [...group.items]).find(item => item.id === view)!;

  useEffect(() => { currentView.current = view; }, [view]);
  useEffect(() => { currentToken.current = tokens?.access_token; }, [tokens?.access_token]);

  useEffect(() => {
    if (!isAuthenticated || !user || manualSync || demoMode) return;
    const run = new AbortController();
    prefetchRun.current = run;
    const timer = window.setTimeout(async () => {
      await prefetchSection(currentView.current, canEdit, showDrive);
      for (const next of prefetchOrder) {
        if (run.signal.aborted) break;
        if (next !== currentView.current) await prefetchSection(next, canEdit, showDrive);
      }
    }, 300);
    return () => { run.abort(); window.clearTimeout(timer); };
  }, [isAuthenticated, user, manualSync, version, canEdit, showDrive]);

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
    document.getElementById('workspace-menu-toggle')?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebar(false);
        document.getElementById('workspace-menu-toggle')?.focus();
      }
    };
    window.addEventListener('keydown', close);
    return () => {
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

  async function syncNow() {
    const token = tokens?.access_token;
    prefetchRun.current?.abort();
    setManualSync(true);
    setSyncMessage('');
    try {
      const result = await apiClient.syncDriveNow();
      if (token !== currentToken.current) return;
      if (result.status === 'error') throw new Error(result.message ?? 'Ошибка синхронизации');
      clearSectionData();
      const status = await apiClient.getDriveSyncStatus().catch(() => null);
      if (token !== currentToken.current) return;
      let active: Section;
      do {
        active = currentView.current;
        await prefetchSection(active, canEdit, canEdit && !demoMode && (status?.drive_mode ?? sync?.drive_mode) !== 'mock');
      } while (token === currentToken.current && active !== currentView.current);
      if (token !== currentToken.current) return;
      if (status) setSync(status);
      setSyncMessage(result.message ?? 'Синхронизация завершена');
      setVersion(value => value + 1);
    } catch (error) {
      if (token === currentToken.current) setSyncMessage(error instanceof Error ? error.message : 'Не удалось запустить синхронизацию');
    } finally {
      setManualSync(false);
    }
  }

  if (isLoading) return <main className="workspace-loading"><DataLoading /></main>;
  if (!isAuthenticated) return <AuthPage />;

  const isSyncing = manualSync || sync?.status === 'syncing';
  const lastSync = Date.parse(sync?.last_synced_at ?? '');
  const syncLabel = sync?.status === 'syncing' ? 'Идёт импорт' : sync?.status === 'error' ? 'Ошибка импорта' : Number.isFinite(lastSync) ? formatSync.format(lastSync) : 'Google Drive';
  const customerView = customerViews.includes(view);

  function renderPageHeader(actions?: ReactNode) {
    return <header className="workspace-heading workspace-pagebar">
      <div><div className="workspace-eyebrow"><section.icon size={15} /> ENTERPRISE HUB</div><h1>{section.label}</h1><p>{section.description}</p></div>
      <div className="workspace-pagebar-actions">
        {actions}
        <button type="button" className="workspace-icon-button workspace-home-button" aria-label="К обзору" title="К обзору" onClick={() => navigate('summary')}><House size={17} /></button>
      </div>
    </header>;
  }

  function renderSection() {
    switch (view) {
      case 'engineers': return demoMode ? <p>Реестр доступен в рабочей организации.</p> : canEdit ? <EngineerDocumentsTab refreshAt={sync?.last_synced_at} onHome={() => navigate('summary')} /> : <p>Раздел доступен руководителям организации.</p>;
      case 'projects': return <ProjectsTab renderHeader={renderPageHeader} />;
      case 'finance': return <FinanceTab />;
      case 'procurement': return <ProcurementTab key={String(procurementDue)} dueOnly={procurementDue} renderHeader={renderPageHeader} />;
      case 'dispatch': return <DispatchTab renderHeader={renderPageHeader} driveLink={demoMode ? undefined : sync?.root_folder_link} />;
      case 'tasks': return <TasksTab renderHeader={renderPageHeader} />;
      case 'files': return <FilesTab showDrive={showDrive} onFileSelect={canEdit ? (id, name) => setMapping({ id, name }) : undefined} />;
      case 'settings': return <SettingsTab />;
      default: return null;
    }
  }

  return (
    <div className="workspace" data-sidebar={sidebar ? 'open' : 'closed'}>
      <header className="workspace-topbar">
        <div className="workspace-topbar-strip"><div className="workspace-topbar-start">
          <a href="#summary" className="workspace-brand" aria-label="Enterprise Hub — обзор" onClick={event => { event.preventDefault(); navigate('summary'); }}>
            <span className="workspace-brand-mark"><Workflow size={18} />

            </span><strong>Enterprise Hub</strong>
          </a>
          <span className="workspace-current"><ChevronRight size={13} />{section.label}</span>
        </div>
        <div className="workspace-topbar-actions">
          {demoMode && <span className="workspace-demo" title="Учебные данные"><FlaskConical size={14} />Демо</span>}
          {!demoMode && (
            <button className="workspace-sync" onClick={syncNow} disabled={isSyncing}
              title={isSyncing ? 'Синхронизация…' : syncMessage || syncLabel}
              aria-label={isSyncing ? 'Идёт синхронизация Google Диска' : 'Синхронизировать Google Диск'}
              aria-busy={isSyncing}>
              {isSyncing ? <LoaderCircle size={15} className="motion-safe:animate-spin" aria-hidden="true" /> : <Database size={15} aria-hidden="true" />}
              <span>{isSyncing ? 'Синхронизация…' : 'Синхронизировать'}</span>
            </button>
          )}
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
        <nav className="workspace-tabs" aria-label="Быстрый доступ к разделам"><div className="workspace-tabs-title"><strong>Панель руководителя</strong></div>
          {[
            { label: 'Обзор', ids: ['summary'] },
            { label: 'Контракты', ids: ['registry', 'projects'] },
            { label: 'Финансы', ids: ['finance'] },
            { label: 'Операции', ids: ['procurement', 'dispatch', 'tasks', ...(!demoMode && canEdit ? ['engineers'] : [])] },
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
            onAccounting={canEdit && (demoMode || sync?.drive_mode === 'mock') ? () => setUpload('accounting') : undefined}
            driveLink={demoMode ? undefined : sync?.root_folder_link}
          /></Suspense>}
        </nav>
      </header>
      <aside id="workspace-sidebar" className="workspace-sidebar" aria-label="Навигация">
        <div className="workspace-sidebar-head">
          <button id="workspace-menu-toggle" type="button" className="workspace-icon-button"
            aria-controls="workspace-sidebar" aria-expanded={sidebar}
            aria-label={sidebar ? 'Свернуть разделы' : 'Развернуть разделы'}
            title={sidebar ? 'Свернуть разделы' : 'Развернуть разделы'}
            onClick={() => setSidebar(open => !open)}>
            {sidebar ? <PanelLeftClose size={19} aria-hidden="true" /> : <PanelLeftOpen size={19} aria-hidden="true" />}
          </button>
        </div>
        <nav aria-label="Разделы">
          {sections.map(group => <div className="workspace-nav-group" key={group.title}>
            <p>{group.title}</p>
            {group.items.map(({ id, label, icon: Icon }) => <a key={id} href={`#${id}`} aria-label={label} title={label} aria-current={view === id ? 'page' : undefined} onClick={event => { if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; event.preventDefault(); navigate(id); }}><Icon size={18} /><span>{label}</span></a>)}
          </div>)}
        </nav>
      </aside>
      <main className="workspace-main" data-view={view}>
        {syncMessage && <p role="status">{syncMessage}</p>}
        {customerView ? <CustomerTendersTab key={version} view={view as TenderView} onViewChange={navigate} penalties={penalties} onOpenAlerts={() => setShowAlerts('penalties')} onOpenProcurement={() => navigate('procurement', true)} onOpenFinance={() => navigate('finance')} />
          : <>
              {view === 'files' ? renderPageHeader(<>
                {!demoMode && canEdit && sync?.root_folder_link && <a className="workspace-catalog-button" href={sync.root_folder_link} target="_blank" rel="noreferrer"><ExternalLink size={16} />Папка Google Диска</a>}
                {canEdit && <button type="button" className="workspace-catalog-button" onClick={() => setUpload('file')}><Upload size={16} />Загрузить файл</button>}
              </>) : (view === 'settings' || (view === 'engineers' && (demoMode || !canEdit))) && renderPageHeader()}
              <div key={`${view}-${version}`} className="workspace-module workspace-reveal"><Suspense fallback={<DataLoading />}>{renderSection()}</Suspense></div>
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
