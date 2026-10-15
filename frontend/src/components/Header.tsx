import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import {
  BarChart3,
  Bell,
  Moon,
  Sun,
  LogOut,
  User,
  ChevronDown,
  Settings as SettingsIcon,
} from 'lucide-react';
import { Select } from '@/components/Select';

interface HeaderProps {
  period: string;
  onPeriodChange: (value: string) => void;
  alertsCount: number;
  onAlertsClick: () => void;
  onOpenSettings?: () => void;
}

const periodOptions = [
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
];

export function Header({
  period,
  onPeriodChange,
  alertsCount,
  onAlertsClick,
  onOpenSettings,
}: HeaderProps) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        {/* Left: Logo */}
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-md bg-indigo-600">
            <BarChart3 className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 hidden sm:inline">
            Smart Enterprise Hub
          </span>
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <Select
            options={periodOptions}
            value={period}
            onChange={onPeriodChange}
            className="w-28 hidden sm:block"
            id="header-period-select"
          />

          {/* Alerts bell */}
          <button
            onClick={onAlertsClick}
            className="relative p-2 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Уведомления"
            id="header-alerts-btn"
          >
            <Bell className="h-5 w-5" />
            {alertsCount > 0 && (
              <span className="absolute top-1 right-1 h-4 min-w-4 px-1 flex items-center justify-center rounded-full bg-rose-600 text-white text-[10px] font-medium">
                {alertsCount}
              </span>
            )}
          </button>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="p-2 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Переключить тему"
            id="header-theme-toggle"
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>

          {/* Profile */}
          <div className="relative">
            <button
              onClick={() => setProfileOpen(!profileOpen)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-md text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              id="header-profile-btn"
            >
              <div className="h-7 w-7 rounded-full bg-indigo-600 flex items-center justify-center">
                <User className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-sm font-medium hidden md:inline">
                {user?.full_name?.split(' ').slice(0, 2).join(' ') || 'Профиль'}
              </span>
              <ChevronDown className="h-3.5 w-3.5 hidden md:inline" />
            </button>

            {profileOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
                <div className="absolute right-0 mt-1 w-56 z-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md shadow-lg py-1">
                  <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-700">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{user?.full_name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
                  </div>
                  {onOpenSettings && (
                    <button
                      onClick={() => {
                        setProfileOpen(false);
                        onOpenSettings();
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      id="header-settings-item"
                    >
                      <SettingsIcon className="h-4 w-4" />
                      Настройки системы
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    id="header-logout-item"
                  >
                    <LogOut className="h-4 w-4" />
                    Выйти
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
