import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/context/ToastContext';
import { apiClient } from '@/api/client';
import { formatRelativeTime } from '@/utils/format';
import {
  BarChart3,
  Bell,
  Moon,
  Sun,
  LogOut,
  User,
  ChevronDown,
  Settings as SettingsIcon,
  RefreshCw,
  Menu,
  X,
  LayoutDashboard,
  Building2,
  Wallet,
  ShoppingBag,
  Radio,
  CheckSquare,
  FolderGit2,
} from 'lucide-react';
import { Select } from '@/components/Select';

interface HeaderProps {
  period: string;
  onPeriodChange: (value: string) => void;
  alertsCount: number;
  onAlertsClick: () => void;
  onOpenSettings?: () => void;
  onNavigateTab?: (tabId: string) => void;
  activeTab?: string;
  onSyncComplete?: () => void;
}

const periodOptions = [
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
];

const NAVIGATION_SECTIONS = [
  { id: 'summary', label: 'Сводка и риски', icon: LayoutDashboard },
  { id: 'tenders', label: 'Тендеры и объекты', icon: Building2 },
  { id: 'finance', label: 'Финансы и касса', icon: Wallet },
  { id: 'procurement', label: 'Снабжение и закупки', icon: ShoppingBag },
  { id: 'dispatch', label: 'Диспетчерская', icon: Radio },
  { id: 'tasks', label: 'Смарт-реестр задач', icon: CheckSquare },
  { id: 'files', label: 'Файлы и Google Диск', icon: FolderGit2 },
];

export function Header({
  period,
  onPeriodChange,
  alertsCount,
  onAlertsClick,
  onOpenSettings,
  onNavigateTab,
  activeTab = 'summary',
  onSyncComplete,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const { showToast } = useToast();

  const [profileOpen, setProfileOpen] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);

  // Load sync status on mount
  useEffect(() => {
    let mounted = true;
    apiClient
      .getDriveSyncStatus()
      .then((status) => {
        if (mounted && status?.last_synced_at) {
          setLastSyncedAt(status.last_synced_at);
        }
      })
      .catch(() => {
        if (mounted) {
          setLastSyncedAt(null);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleSyncDrive = async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      const result = await apiClient.syncDriveNow();
      if (result.status === 'error') throw new Error(result.message || 'Ошибка синхронизации');
      setLastSyncedAt(result.last_synced_at || new Date().toISOString());
      onSyncComplete?.();
      showToast(
        result.message ||
          `Синхронизация с Google Диском завершена: обновлено ${result.synced_files_count} файлов`,
        'success'
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка при обращении к Google Drive';
      showToast(msg, 'error');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSelectNavSection = (id: string) => {
    if (onNavigateTab) {
      onNavigateTab(id);
    }
    setMobileDrawerOpen(false);
  };

  return (
    <>
      <header className="sticky top-0 z-40 bg-[var(--header-bg)] backdrop-blur-md border-b border-[var(--card-border)] transition-colors">
        <div className="max-w-screen-2xl mx-auto px-3 sm:px-6 h-14 flex items-center justify-between gap-2 sm:gap-4">
          {/* Left: Minimalist Brand Logo & System Title (title hidden on mobile) */}
          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            <div className="p-2 rounded-xl bg-slate-950 text-white dark:bg-white dark:text-slate-950 shadow-2xs flex items-center justify-center transition-colors">
              <BarChart3 className="h-4 w-4" />
            </div>
            <div className="hidden md:flex flex-col">
              <span className="text-sm font-semibold tracking-tight text-[var(--text-main)] leading-none">
                Smart Enterprise Hub
              </span>
              <span className="text-[10px] text-[var(--text-muted)] mt-0.5 font-medium">
                Операционный пульт управления
              </span>
            </div>
          </div>

          {/* Right: Controls & Actions (Sync, Alerts, Theme, Burger on mobile) */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {/* Google Drive Sync Button */}
            <button
              type="button"
              onClick={handleSyncDrive}
              disabled={isSyncing}
              className="min-h-[38px] min-w-[38px] p-2 md:px-3 md:py-1.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] hover:bg-[var(--card-subtle)] text-[var(--text-main)] text-xs font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer shadow-2xs"
              title="Синхронизировать с корпоративным Google Диском"
              aria-label="Синхронизировать Google Диск"
              id="header-drive-sync-btn"
            >
              <RefreshCw
                className={`h-4 w-4 md:h-3.5 md:w-3.5 text-[var(--text-sub)] shrink-0 ${
                  isSyncing ? 'animate-spin' : ''
                }`}
              />
              <div className="hidden md:flex flex-col text-left leading-tight">
                <span className="font-semibold text-[var(--text-main)] text-[11px]">
                  {isSyncing ? 'Синхронизация...' : 'Синхронизировать Диск'}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">
                  {formatRelativeTime(lastSyncedAt)}
                </span>
              </div>
            </button>

            {/* Period selector (desktop/tablet only) */}
            <Select
              options={periodOptions}
              value={period}
              onChange={onPeriodChange}
              size="sm"
              className="w-24 sm:w-28 hidden lg:block"
              id="header-period-select"
            />

            {/* Alerts Bell Button */}
            <button
              type="button"
              onClick={onAlertsClick}
              className="min-h-[38px] min-w-[38px] p-2 rounded-xl text-[var(--text-sub)] hover:text-[var(--text-main)] bg-[var(--card-bg)] hover:bg-[var(--card-subtle)] transition-colors relative flex items-center justify-center cursor-pointer border border-[var(--card-border)] shadow-2xs"
              aria-label="Уведомления и горящие риски"
              id="header-alerts-btn"
            >
              <Bell className="h-4.5 w-4.5" />
              {alertsCount > 0 && (
                <span className="absolute top-1.5 right-1.5 h-4 min-w-4 px-1 flex items-center justify-center rounded-full bg-red-600 text-white text-[10px] font-semibold leading-none shadow-xs">
                  {alertsCount}
                </span>
              )}
            </button>

            {/* Theme Toggle (Light / Dark) */}
            <button
              type="button"
              onClick={toggle}
              className="min-h-[38px] min-w-[38px] p-2 rounded-xl bg-[var(--card-bg)] text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors flex items-center justify-center cursor-pointer border border-[var(--card-border)] shadow-2xs"
              aria-label="Переключить тему"
              id="header-theme-toggle"
            >
              {isDark ? <Sun className="h-4.5 w-4.5" /> : <Moon className="h-4.5 w-4.5" />}
            </button>

            {/* Desktop User Profile */}
            <div className="relative hidden md:block">
              <button
                type="button"
                onClick={() => setProfileOpen(!profileOpen)}
                className="min-h-[38px] flex items-center gap-2 px-2 py-1.5 rounded-xl text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer border border-transparent hover:border-[var(--card-border)]"
                id="header-profile-btn"
              >
                <div className="h-7 w-7 rounded-lg bg-[var(--text-main)] text-[var(--canvas-bg)] flex items-center justify-center font-semibold text-xs shrink-0 shadow-2xs">
                  <User className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-semibold text-[var(--text-main)] max-w-[120px] truncate">
                  {user?.full_name?.split(' ').slice(0, 2).join(' ') || 'Профиль'}
                </span>
                <ChevronDown className="h-3 w-3 text-[var(--text-muted)]" />
              </button>

              {profileOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
                  <div className="absolute right-0 mt-1.5 w-60 z-20 bg-[var(--card-bg)] border border-[var(--card-border)] rounded-2xl shadow-xl py-1.5 text-[var(--text-main)] animate-in fade-in zoom-in-95 duration-100">
                    <div className="px-3.5 py-2.5 border-b border-[var(--card-border)]">
                      <p className="text-xs font-semibold text-[var(--text-main)] truncate">
                        {user?.full_name}
                      </p>
                      <p className="text-[11px] text-[var(--text-sub)] truncate">{user?.email}</p>
                    </div>

                    {onOpenSettings && (
                      <button
                        type="button"
                        onClick={() => {
                          setProfileOpen(false);
                          onOpenSettings();
                        }}
                        className="min-h-[40px] w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer"
                        id="header-settings-item"
                      >
                        <SettingsIcon className="h-4 w-4 text-[var(--text-muted)]" />
                        <span>Настройки системы</span>
                      </button>
                    )}

                    <div className="border-t border-[var(--card-border)] my-1" />

                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        logout();
                      }}
                      className="min-h-[40px] w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-50/80 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
                      id="header-logout-item"
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Выйти из системы</span>
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Mobile Burger Button (FE-4.1) */}
            <button
              type="button"
              onClick={() => setMobileDrawerOpen(true)}
              className="md:hidden min-h-[38px] min-w-[38px] p-2 rounded-xl bg-[var(--card-subtle)] text-[var(--text-main)] border border-[var(--card-border)] transition-colors flex items-center justify-center cursor-pointer shadow-2xs"
              aria-label="Открыть мобильное меню"
              id="header-mobile-burger-btn"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Navigation Drawer (FE-4.1) */}
      {mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
            onClick={() => setMobileDrawerOpen(false)}
          />

          {/* Drawer Sidebar */}
          <div className="relative ml-auto w-5/6 max-w-sm h-full bg-[var(--card-bg)] border-l border-[var(--card-border)] shadow-2xl p-5 flex flex-col justify-between overflow-y-auto z-10 animate-in slide-in-from-right duration-200">
            <div className="space-y-5">
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-3 border-b border-[var(--card-border)]">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-slate-950 text-white dark:bg-white dark:text-slate-950 shadow-2xs">
                    <BarChart3 className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-[var(--text-main)] leading-none">
                      Smart Enterprise Hub
                    </h3>
                    <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                      Навигация по разделам
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileDrawerOpen(false)}
                  className="min-h-[38px] min-w-[38px] flex items-center justify-center rounded-xl text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer"
                  aria-label="Закрыть меню"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Navigation Sections */}
              <div className="space-y-1.5">
                <span className="text-[11px] uppercase font-semibold text-[var(--text-muted)] tracking-wider">
                  Разделы платформы:
                </span>
                <div className="space-y-1">
                  {NAVIGATION_SECTIONS.map((sec) => {
                    const Icon = sec.icon;
                    const isActive = activeTab === sec.id;

                    return (
                      <button
                        key={sec.id}
                        type="button"
                        onClick={() => handleSelectNavSection(sec.id)}
                        className={`w-full min-h-[44px] flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer text-left ${
                          isActive
                            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs'
                            : 'bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)] border border-[var(--card-border)]'
                        }`}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{sec.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Google Drive Sync Quick Action in Drawer */}
              <div className="pt-2 border-t border-[var(--card-border)]">
                <button
                  type="button"
                  onClick={handleSyncDrive}
                  disabled={isSyncing}
                  className="w-full min-h-[44px] px-3.5 py-2.5 rounded-xl border border-[var(--card-border)] bg-[var(--card-subtle)] hover:bg-[var(--card-bg)] text-[var(--text-main)] text-xs font-semibold transition-all flex items-center justify-between cursor-pointer shadow-2xs"
                >
                  <div className="flex items-center gap-2">
                    <RefreshCw className={`h-4 w-4 text-[var(--text-sub)] shrink-0 ${isSyncing ? 'animate-spin' : ''}`} />
                    <span>Синхронизировать Google Диск</span>
                  </div>
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {formatRelativeTime(lastSyncedAt)}
                  </span>
                </button>
              </div>
            </div>

            {/* Drawer Footer: User Profile & Logout */}
            <div className="pt-4 border-t border-[var(--card-border)] space-y-3">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-xl bg-[var(--text-main)] text-[var(--canvas-bg)] flex items-center justify-center font-bold text-xs shrink-0">
                  <User className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-[var(--text-main)] truncate">
                    {user?.full_name}
                  </p>
                  <p className="text-[10px] text-[var(--text-muted)] truncate">{user?.email}</p>
                </div>
              </div>

              {onOpenSettings && (
                <button
                  type="button"
                  onClick={() => {
                    setMobileDrawerOpen(false);
                    onOpenSettings();
                  }}
                  className="w-full min-h-[40px] flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] transition-colors cursor-pointer"
                >
                  <SettingsIcon className="h-4 w-4" />
                  <span>Настройки системы</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => {
                  setMobileDrawerOpen(false);
                  logout();
                }}
                className="w-full min-h-[40px] flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 hover:bg-red-100 transition-colors cursor-pointer"
              >
                <LogOut className="h-4 w-4" />
                <span>Выйти из аккаунта</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
