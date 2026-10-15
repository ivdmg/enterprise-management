import { useState } from 'react';
import {
  LayoutDashboard,
  Building2,
  Wallet,
  ShoppingBag,
  Radio,
  CheckSquare,
  FolderGit2,
  Menu,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useRole } from '@/context/RoleContext';

export interface TabItem {
  id: string;
  label: string;
  shortLabel?: string;
  badge?: number | string;
}

interface TabNavProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

const TAB_ICONS: Record<string, LucideIcon> = {
  summary: LayoutDashboard,
  tenders: Building2,
  finance: Wallet,
  procurement: ShoppingBag,
  dispatch: Radio,
  tasks: CheckSquare,
  files: FolderGit2,
};

export function TabNav({ tabs, activeTab, onChange }: TabNavProps) {
  const { isRoleFocusedTab, currentRoleDef } = useRole();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // For mobile bottom bar: select 4 most relevant tabs based on role + "More"
  const prioritizedTabs = [...tabs].sort((a, b) => {
    const aFocus = isRoleFocusedTab(a.id) ? 1 : 0;
    const bFocus = isRoleFocusedTab(b.id) ? 1 : 0;
    return bFocus - aFocus;
  });
  const bottomBarTabs = prioritizedTabs.slice(0, 4);

  const handleTabClick = (tabId: string) => {
    onChange(tabId);
    setMobileMenuOpen(false);
  };

  return (
    <>
      {/* ============================================================ */}
      {/* DESKTOP & TABLET TOP TAB BAR (>= 768px)                       */}
      {/* ============================================================ */}
      <nav
        className="hidden md:block border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/40 backdrop-blur-xs"
        id="main-tab-nav"
      >
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
          <div className="flex gap-2 -mb-px overflow-x-auto scrollbar-none py-1">
            {tabs.map((tab) => {
              const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
              const isActive = activeTab === tab.id;
              const isFocused = isRoleFocusedTab(tab.id);

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleTabClick(tab.id)}
                  className={`min-h-[44px] px-3.5 py-2 text-xs lg:text-sm font-medium whitespace-nowrap border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                    isActive
                      ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 font-semibold'
                      : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700'
                  }`}
                  id={`tab-${tab.id}`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 ${
                      isActive
                        ? 'text-indigo-600 dark:text-indigo-400'
                        : 'text-slate-400 dark:text-slate-500'
                    }`}
                  />
                  <span>{tab.label}</span>

                  {/* Focus pill for role */}
                  {isFocused && (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400"
                      title={`Фокусная вкладка для роли: ${currentRoleDef.shortName}`}
                    />
                  )}

                  {/* Optional numeric badge */}
                  {tab.badge !== undefined && (
                    <span
                      className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${
                        isActive
                          ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                          : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                      }`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* ============================================================ */}
      {/* MOBILE TOP HORIZONTAL PILLS (< 768px)                         */}
      {/* ============================================================ */}
      <div className="md:hidden border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 overflow-x-auto scrollbar-none px-3 py-1.5 flex gap-1.5">
        {tabs.map((tab) => {
          const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTabClick(tab.id)}
              className={`min-h-[44px] px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap flex items-center gap-1.5 transition-colors cursor-pointer ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{tab.shortLabel || tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ============================================================ */}
      {/* MOBILE BOTTOM NAVIGATION BAR (< 768px)                       */}
      {/* ============================================================ */}
      <div
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 pb-[max(0.5rem,env(safe-area-inset-bottom))]"
        id="mobile-bottom-nav"
      >
        <div className="grid grid-cols-5 h-14">
          {bottomBarTabs.map((tab) => {
            const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleTabClick(tab.id)}
                className={`min-h-[44px] flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors cursor-pointer ${
                  isActive
                    ? 'text-indigo-600 dark:text-indigo-400 font-semibold'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
                id={`mobile-nav-${tab.id}`}
              >
                <Icon className="h-4 w-4" />
                <span className="truncate max-w-[64px]">{tab.shortLabel || tab.label}</span>
              </button>
            );
          })}

          {/* More / Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="min-h-[44px] flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
            id="mobile-nav-more"
          >
            <Menu className="h-4 w-4" />
            <span>Разделы</span>
          </button>
        </div>
      </div>

      {/* ============================================================ */}
      {/* MOBILE SLIDE-UP DRAWER FOR ALL 7 TABS                        */}
      {/* ============================================================ */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex flex-col justify-end">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 rounded-t-2xl p-4 pb-8 space-y-3 shadow-2xl max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  Все разделы хаба
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Роль: {currentRoleDef.name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                aria-label="Закрыть меню"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2 pt-1">
              {tabs.map((tab) => {
                const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
                const isActive = activeTab === tab.id;
                const isFocused = isRoleFocusedTab(tab.id);

                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => handleTabClick(tab.id)}
                    className={`min-h-[48px] w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border text-sm font-medium transition-all ${
                      isActive
                        ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200'
                        : 'border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-850 text-slate-800 dark:text-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2 rounded-lg ${
                          isActive
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium">{tab.label}</p>
                        {isFocused && (
                          <p className="text-[10px] text-indigo-600 dark:text-indigo-400">
                            Фокус роли {currentRoleDef.shortName}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
