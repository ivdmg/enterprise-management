import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useRole } from '@/context/RoleContext';
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
  Crown,
  ShieldCheck,
  Briefcase,
  HardHat,
  Radio,
  Layers,
  Scale,
  ShoppingBag,
  Receipt,
  Users,
} from 'lucide-react';
import { Select } from '@/components/Select';
import { RoleSwitcherModal } from '@/components/RoleSwitcherModal';

interface HeaderProps {
  period: string;
  onPeriodChange: (value: string) => void;
  alertsCount: number;
  onAlertsClick: () => void;
  onOpenSettings?: () => void;
  onNavigateTab?: (tabId: string) => void;
}

const periodOptions = [
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
];

function getRoleIcon(iconName: string) {
  const iconProps = { className: 'h-3.5 w-3.5 shrink-0' };
  switch (iconName) {
    case 'Crown':
      return <Crown {...iconProps} />;
    case 'ShieldCheck':
      return <ShieldCheck {...iconProps} />;
    case 'Briefcase':
      return <Briefcase {...iconProps} />;
    case 'HardHat':
      return <HardHat {...iconProps} />;
    case 'Radio':
      return <Radio {...iconProps} />;
    case 'Layers':
      return <Layers {...iconProps} />;
    case 'Scale':
      return <Scale {...iconProps} />;
    case 'ShoppingBag':
      return <ShoppingBag {...iconProps} />;
    case 'Receipt':
      return <Receipt {...iconProps} />;
    default:
      return <Briefcase {...iconProps} />;
  }
}

export function Header({
  period,
  onPeriodChange,
  alertsCount,
  onAlertsClick,
  onOpenSettings,
  onNavigateTab,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const { currentRoleDef } = useRole();
  const { showToast } = useToast();

  const [profileOpen, setProfileOpen] = useState(false);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
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
          setLastSyncedAt(new Date(Date.now() - 15 * 60 * 1000).toISOString());
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
      setLastSyncedAt(result.last_synced_at || new Date().toISOString());
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

  return (
    <>
      <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800 transition-colors">
        <div className="max-w-screen-2xl mx-auto px-3 sm:px-6 h-14 flex items-center justify-between gap-2 sm:gap-4">
          {/* Left: Minimalist Brand Logo & Role Pill */}
          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            {/* White & Gray Bento-Box Logo */}
            <div className="p-2 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-2xs flex items-center justify-center transition-colors">
              <BarChart3 className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100 hidden sm:inline leading-none">
                Smart Enterprise Hub
              </span>
              <span className="text-[10px] text-slate-400 dark:text-slate-500 hidden sm:inline mt-0.5 font-medium">
                Операционный пульт
              </span>
            </div>

            {/* Role Switcher Pill */}
            <button
              type="button"
              onClick={() => setRoleModalOpen(true)}
              className="min-h-[38px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 text-slate-800 dark:text-slate-200 border border-slate-200/80 dark:border-slate-700/80 transition-colors flex items-center gap-1.5 text-xs font-medium cursor-pointer shadow-2xs"
              title="Переключить активную роль"
              id="header-role-switcher-btn"
            >
              <span className="text-slate-700 dark:text-slate-300">
                {getRoleIcon(currentRoleDef.iconName)}
              </span>
              <span className="max-w-[90px] sm:max-w-none truncate">{currentRoleDef.shortName}</span>
              <ChevronDown className="h-3 w-3 text-slate-400" />
            </button>
          </div>

          {/* Right: Controls & Actions */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Google Drive Sync Button */}
            <button
              type="button"
              onClick={handleSyncDrive}
              disabled={isSyncing}
              className="min-h-[38px] px-2.5 sm:px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/80 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors flex items-center gap-2 disabled:opacity-60 cursor-pointer shadow-2xs"
              title="Синхронизировать с корпоративным Google Диском"
              id="header-drive-sync-btn"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 text-slate-600 dark:text-slate-400 shrink-0 ${
                  isSyncing ? 'animate-spin' : ''
                }`}
              />
              <div className="hidden md:flex flex-col text-left leading-tight">
                <span className="font-semibold text-slate-900 dark:text-slate-100 text-[11px]">
                  {isSyncing ? 'Синхронизация...' : 'Синхронизировать Диск'}
                </span>
                <span className="text-[10px] text-slate-400 dark:text-slate-500">
                  {formatRelativeTime(lastSyncedAt)}
                </span>
              </div>
            </button>

            {/* Period selector (desktop/tablet) */}
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
              className="min-h-[38px] min-w-[38px] p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative flex items-center justify-center cursor-pointer"
              aria-label="Уведомления и горящие риски"
              id="header-alerts-btn"
            >
              <Bell className="h-4.5 w-4.5" />
              {alertsCount > 0 && (
                <span className="absolute top-1.5 right-1.5 h-4 min-w-4 px-1 flex items-center justify-center rounded-full bg-rose-600 text-white text-[10px] font-semibold leading-none shadow-xs">
                  {alertsCount}
                </span>
              )}
            </button>

            {/* Theme Toggle (Light / Dark) */}
            <button
              type="button"
              onClick={toggle}
              className="min-h-[38px] min-w-[38px] p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center justify-center cursor-pointer border border-slate-200/60 dark:border-slate-700/60 shadow-2xs"
              aria-label="Переключить тему"
              id="header-theme-toggle"
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            {/* User Profile */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen(!profileOpen)}
                className="min-h-[38px] flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-200/60 dark:hover:border-slate-700/60"
                id="header-profile-btn"
              >
                <div className="h-7 w-7 rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 flex items-center justify-center font-semibold text-xs shrink-0 shadow-2xs">
                  <User className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 hidden md:inline max-w-[120px] truncate">
                  {user?.full_name?.split(' ').slice(0, 2).join(' ') || 'Профиль'}
                </span>
                <ChevronDown className="h-3 w-3 hidden md:inline text-slate-400" />
              </button>

              {profileOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
                  <div className="absolute right-0 mt-1.5 w-64 z-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl py-1 text-slate-700 dark:text-slate-300 animate-in fade-in zoom-in-95 duration-100">
                    <div className="px-3.5 py-2.5 border-b border-slate-100 dark:border-slate-800">
                      <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                        {user?.full_name}
                      </p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
                      <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-800 dark:text-slate-200 font-medium">
                        {getRoleIcon(currentRoleDef.iconName)}
                        <span>{currentRoleDef.name}</span>
                      </div>
                    </div>

                    {/* Role switcher menu item */}
                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        setRoleModalOpen(true);
                      }}
                      className="min-h-[40px] w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                      id="header-switch-role-item"
                    >
                      <Users className="h-4 w-4 text-slate-500" />
                      <span>Сменить активную роль (9 ролей)</span>
                    </button>

                    {onOpenSettings && (
                      <button
                        type="button"
                        onClick={() => {
                          setProfileOpen(false);
                          onOpenSettings();
                        }}
                        className="min-h-[40px] w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                        id="header-settings-item"
                      >
                        <SettingsIcon className="h-4 w-4 text-slate-400" />
                        <span>Настройки системы</span>
                      </button>
                    )}

                    <div className="border-t border-slate-100 dark:border-slate-800 my-1" />

                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        logout();
                      }}
                      className="min-h-[40px] w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors cursor-pointer"
                      id="header-logout-item"
                    >
                      <LogOut className="h-4 w-4" />
                      <span>Выйти из системы</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Role Switcher Modal */}
      <RoleSwitcherModal
        isOpen={roleModalOpen}
        onClose={() => setRoleModalOpen(false)}
        onRoleSelected={(targetTab) => {
          if (targetTab && onNavigateTab) {
            onNavigateTab(targetTab);
          }
        }}
      />
    </>
  );
}
