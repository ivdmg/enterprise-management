import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { AuthPage } from '@/features/auth/AuthPage';
import { Header } from '@/components/Header';
import { TabNav } from '@/components/TabNav';
import { DashboardTab } from '@/features/dashboard/DashboardTab';
import { FinanceTab } from '@/features/dashboard/FinanceTab';
import { ProjectsTab } from '@/features/dashboard/ProjectsTab';
import { PayrollTab } from '@/features/dashboard/PayrollTab';
import { FilesTab } from '@/features/files/FilesTab';
import { SettingsTab } from '@/features/settings/SettingsTab';
import { FileUploadModal } from '@/features/files/FileUploadModal';
import { MappingDrawer } from '@/features/files/MappingDrawer';
import { AlertsDrawer } from '@/features/alerts/AlertsDrawer';

const TABS = [
  { id: 'summary', label: 'Сводка' },
  { id: 'finance', label: 'Финансы' },
  { id: 'projects', label: 'Тендеры и объекты' },
  { id: 'payroll', label: 'ФОТ' },
  { id: 'files', label: 'Файлы' },
  { id: 'settings', label: 'Настройки' },
];

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState('summary');
  const [period, setPeriod] = useState('month');
  const [showAlerts, setShowAlerts] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [mappingFile, setMappingFile] = useState<{ id: string; name: string } | null>(null);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
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
        return <DashboardTab />;
      case 'finance':
        return <FinanceTab />;
      case 'projects':
        return <ProjectsTab />;
      case 'payroll':
        return <PayrollTab />;
      case 'files':
        return (
          <FilesTab
            onUploadClick={() => setShowUpload(true)}
            onFileSelect={(id, name) => setMappingFile({ id, name })}
          />
        );
      case 'settings':
        return <SettingsTab />;
      default:
        return <DashboardTab />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Header
        period={period}
        onPeriodChange={setPeriod}
        alertsCount={6}
        onAlertsClick={() => setShowAlerts(true)}
        onOpenSettings={() => setActiveTab('settings')}
      />
      <TabNav tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">
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

      <MappingDrawer
        isOpen={!!mappingFile}
        onClose={() => setMappingFile(null)}
        fileId={mappingFile?.id || ''}
        fileName={mappingFile?.name || ''}
      />

      <AlertsDrawer isOpen={showAlerts} onClose={() => setShowAlerts(false)} />
    </div>
  );
}
