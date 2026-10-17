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
      {/* DESKTOP & TABLET TOP SEGMENTED TAB BAR (>= 768px)            */}
      {/* ============================================================ */}
      <nav
        className="hidden md:block border-b border-[var(--card-border)] bg-[var(--header-bg)] backdrop-blur-sm"
        id="main-tab-nav"
      >
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-2.5">
          {/* Bento-Box Segmented Pills Container */}
          <div className="inline-flex items-center bg-[var(--card-subtle)] p-1 rounded-xl border border-[var(--card-subtle-border)] shadow-2xs overflow-x-auto scrollbar-none max-w-full">
            {tabs.map((tab) => {
              const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
              const isActive = activeTab === tab.id;
              const isFocused = isRoleFocusedTab(tab.id);

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleTabClick(tab.id)}
                  className={`min-h-[38px] px-3.5 py-1.5 text-xs lg:text-sm font-medium whitespace-nowrap rounded-lg transition-all flex items-center gap-2 cursor-pointer select-none ${
                    isActive
                      ? 'bg-[var(--card-bg)] text-[var(--text-main)] font-semibold shadow-xs border border-[var(--card-border)]'
                      : 'border border-transparent text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]/60'
                  }`}
                  id={`tab-${tab.id}`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 transition-colors ${
                      isActive
                        ? 'text-[var(--text-main)]'
                        : 'text-[var(--text-muted)]'
                    }`}
                  />
                  <span>{tab.label}</span>

                  {/* Focus pill for role */}
                  {isFocused && (
                    <span
                      className={`h-1.5 w-1.5 rounded-full transition-colors ${
                        isActive
                          ? 'bg-[var(--text-main)]'
                          : 'bg-[var(--text-muted)]'
                      }`}
                      title={`Фокусная вкладка для роли: ${currentRoleDef.shortName}`}
                    />
                  )}

                  {/* Optional numeric badge */}
                  {tab.badge !== undefined && (
                    <span
                      className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-semibold leading-tight ${
                        isActive
                          ? 'bg-[var(--card-subtle)] text-[var(--text-main)] border border-[var(--card-border)]'
                          : 'bg-slate-200 dark:bg-slate-700 text-[var(--text-sub)]'
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
      <div className="md:hidden border-b border-[var(--card-border)] bg-[var(--header-bg)] backdrop-blur-sm overflow-x-auto scrollbar-none px-3 py-2 flex gap-1.5">
        <div className="inline-flex items-center bg-[var(--card-subtle)] p-0.5 rounded-xl border border-[var(--card-subtle-border)]">
          {tabs.map((tab) => {
            const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleTabClick(tab.id)}
                className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap flex items-center gap-1.5 transition-all cursor-pointer ${
                  isActive
                    ? 'bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 font-semibold shadow-xs'
                    : 'text-[var(--text-sub)] hover:text-[var(--text-main)]'
                }`}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span>{tab.shortLabel || tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ============================================================ */}
      {/* MOBILE BOTTOM NAVIGATION BAR (< 768px)                       */}
      {/* ============================================================ */}
      <div
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--header-bg)] backdrop-blur-md border-t border-[var(--card-border)] pb-[max(0.5rem,env(safe-area-inset-bottom))]"
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
                    ? 'text-slate-900 dark:text-slate-100 font-semibold'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
                id={`mobile-nav-${tab.id}`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-slate-900 dark:text-slate-100' : 'text-slate-400'}`} />
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
            <Menu className="h-4 w-4 text-slate-400" />
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
          <div className="relative bg-[var(--card-bg)] border-t border-[var(--card-border)] rounded-t-2xl p-4 pb-8 space-y-3 shadow-2xl max-h-[85vh] overflow-y-auto text-[var(--text-main)]">
            <div className="flex items-center justify-between border-b border-[var(--card-border)] pb-3">
              <div>
                <h3 className="text-base font-semibold text-[var(--text-main)]">
                  Все разделы хаба
                </h3>
                <p className="text-xs text-[var(--text-sub)]">
                  Роль: {currentRoleDef.name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--text-main)] cursor-pointer"
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
                    className={`min-h-[48px] w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border text-sm font-medium transition-all cursor-pointer ${
                      isActive
                        ? 'border-[var(--text-main)] bg-[var(--card-subtle)] text-[var(--text-main)] font-semibold shadow-2xs'
                        : 'border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2 rounded-lg ${
                          isActive
                            ? 'bg-[var(--text-main)] text-[var(--canvas-bg)]'
                            : 'bg-[var(--card-subtle)] text-[var(--text-sub)] border border-[var(--card-border)]'
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium">{tab.label}</p>
                        {isFocused && (
                          <p className="text-[10px] text-[var(--text-muted)]">
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
