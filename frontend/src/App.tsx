import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { AuthPage } from '@/features/auth/AuthPage';
import { Header } from '@/components/Header';
import { TabNav, type TabItem } from '@/components/TabNav';
import { DashboardTab } from '@/features/dashboard/DashboardTab';
import { FinanceTab } from '@/features/dashboard/FinanceTab';
import { ProjectsTab } from '@/features/dashboard/ProjectsTab';
import { ProcurementTab } from '@/features/procurement/ProcurementTab';
import { DispatchTab } from '@/features/dispatch/DispatchTab';
import { TasksTab } from '@/features/tasks/TasksTab';
import { FilesTab } from '@/features/files/FilesTab';
import { SettingsTab } from '@/features/settings/SettingsTab';
import { FileUploadModal } from '@/features/files/FileUploadModal';
import { AccountantUploadModal } from '@/features/files/AccountantUploadModal';
import { MappingDrawer } from '@/features/files/MappingDrawer';
import { AlertsDrawer } from '@/features/alerts/AlertsDrawer';
import { apiClient } from '@/api/client';

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState('summary');
  const [period, setPeriod] = useState('month');
  const [showAlerts, setShowAlerts] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [showAccountantUpload, setShowAccountantUpload] = useState(false);
  const [mappingFile, setMappingFile] = useState<{ id: string; name: string } | null>(null);
  const [pendingAccountingCount, setPendingAccountingCount] = useState(0);
  const [dataVersion, setDataVersion] = useState(0);
  const [alertsCount, setAlertsCount] = useState(0);
  const [highlightProjectId, setHighlightProjectId] = useState<string | null>(null);

  // Poll/fetch pending accounting tasks count
  useEffect(() => {
    if (!isAuthenticated) return;
    let mounted = true;
    apiClient.getAlerts().then((items) => { if (mounted) setAlertsCount(items.length); }).catch(() => {});
    apiClient
      .getTasks({ source: 'accounting', status: 'transferred_to_manager' })
      .then((items) => {
        if (mounted) setPendingAccountingCount(items.length);
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, [activeTab, dataVersion, isAuthenticated]);

  const tabs: TabItem[] = [
    { id: 'summary', label: 'Сводка', shortLabel: 'Сводка' },
    { id: 'tenders', label: 'Тендеры и объекты', shortLabel: 'Тендеры' },
    { id: 'finance', label: 'Финансы и касса', shortLabel: 'Финансы' },
    { id: 'procurement', label: 'Снабжение и закупки', shortLabel: 'Снабжение' },
    { id: 'dispatch', label: 'Диспетчерская', shortLabel: 'Диспетчер' },
    {
      id: 'tasks',
      label: 'Смарт-реестр задач',
      shortLabel: 'Задачи',
      badge: pendingAccountingCount > 0 ? pendingAccountingCount : undefined,
    },
    { id: 'files', label: 'Файлы и Google Диск', shortLabel: 'Файлы' },
  ];

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--canvas-bg)] text-[var(--text-main)] flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-slate-900 dark:border-slate-100 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Auth gate
  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const renderTab = () => {
    switch (activeTab) {
      case 'summary':
        return (
          <DashboardTab
            onNavigateTab={(tab) => setActiveTab(tab)}
            onNavigateToProject={(projectId) => {
              setHighlightProjectId(projectId);
              setActiveTab('tenders');
            }}
          />
        );
      case 'tenders':
        return (
          <ProjectsTab
            highlightProjectId={highlightProjectId}
            onClearHighlight={() => setHighlightProjectId(null)}
          />
        );
      case 'finance':
        return <FinanceTab />;
      case 'procurement':
        return <ProcurementTab />;
      case 'dispatch':
        return <DispatchTab />;
      case 'tasks':
        return <TasksTab />;
      case 'files':
        return (
          <FilesTab
            onUploadClick={() => setShowUpload(true)}
            onAccountantUploadClick={() => setShowAccountantUpload(true)}
            onFileSelect={(id, name) => setMappingFile({ id, name })}
          />
        );
      case 'settings':
        return <SettingsTab />;
      default:
        return (
          <DashboardTab
            onNavigateTab={(tab) => setActiveTab(tab)}
            onNavigateToProject={(projectId) => {
              setHighlightProjectId(projectId);
              setActiveTab('tenders');
            }}
          />
        );
    }
  };

  return (
    <div className="min-h-screen max-w-full overflow-x-hidden bg-[var(--canvas-bg)] text-[var(--text-main)] transition-colors duration-200">
      <Header
        period={period}
        onPeriodChange={setPeriod}
        alertsCount={alertsCount}
        onSyncComplete={() => setDataVersion((v) => v + 1)}
        onAlertsClick={() => setShowAlerts(true)}
        onOpenSettings={() => setActiveTab('settings')}
        onNavigateTab={(tab) => setActiveTab(tab)}
        activeTab={activeTab}
      />
      <TabNav tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      <main key={dataVersion} className="max-w-screen-2xl mx-auto px-3 sm:px-6 py-4 sm:py-6 pb-8 sm:pb-10">
        {renderTab()}
      </main>

      {/* Modals & Drawers */}
      <FileUploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onUploadComplete={(data) => {
          setShowUpload(false);
          setMappingFile({ id: data.file_id, name: data.original_name });
        }}
      />

      <AccountantUploadModal
        isOpen={showAccountantUpload}
        onClose={() => setShowAccountantUpload(false)}
        onUploadSuccess={() => {
          setShowAccountantUpload(false);
          setPendingAccountingCount((c) => c + 1);
          setActiveTab('tasks');
        }}
      />

      <MappingDrawer
        isOpen={!!mappingFile}
        onClose={() => setMappingFile(null)}
        fileId={mappingFile?.id || ''}
        fileName={mappingFile?.name || ''}
      />

      <AlertsDrawer key={dataVersion} isOpen={showAlerts} onClose={() => setShowAlerts(false)} />
    </div>
  );
}
