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
  LayoutGrid,
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

  // For mobile top bar: select 4 most relevant tabs based on role + activeTab fallback
  const prioritizedTabs = [...tabs].sort((a, b) => {
    const aFocus = isRoleFocusedTab(a.id) ? 1 : 0;
    const bFocus = isRoleFocusedTab(b.id) ? 1 : 0;
    return bFocus - aFocus;
  });
  const defaultFour = prioritizedTabs.slice(0, 4);
  const activeTabInFour = defaultFour.some((t) => t.id === activeTab);
  const activeTabObj = tabs.find((t) => t.id === activeTab);

  const displayedMobileTabs =
    activeTabInFour || !activeTabObj
      ? defaultFour
      : [defaultFour[0], defaultFour[1], defaultFour[2], activeTabObj];

  const isMoreSectionActive = !displayedMobileTabs.some((t) => t.id === activeTab);

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
      {/* MOBILE TOP 5-COLUMN SEGMENTED BAR (< 768px)                  */}
      {/* 4 Prioritized Tabs + "Разделы" Drawer Trigger (No Overflow)  */}
      {/* ============================================================ */}
      <div
        className="md:hidden bg-[var(--card-bg)] border-b border-[var(--card-border)] w-full transition-colors shadow-2xs"
        id="mobile-top-nav-bar"
      >
        <div className="grid grid-cols-5 w-full items-center py-1.5 px-0.5">
          {displayedMobileTabs.map((tab) => {
            const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleTabClick(tab.id)}
                className={`min-h-[46px] flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors cursor-pointer select-none py-1 px-0.5 ${
                  isActive
                    ? 'text-[var(--text-main)] font-semibold'
                    : 'text-[var(--text-sub)] hover:text-[var(--text-main)]'
                }`}
                id={`mobile-tab-${tab.id}`}
              >
                <div
                  className={`p-1 rounded-lg transition-all ${
                    isActive
                      ? 'bg-[var(--card-subtle)] border border-[var(--card-border)] text-[var(--text-main)] shadow-2xs'
                      : 'text-[var(--text-muted)]'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <span className="truncate max-w-[58px] leading-tight text-center">
                  {tab.shortLabel || tab.label}
                </span>
              </button>
            );
          })}

          {/* 5th Column: "Разделы" Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className={`min-h-[46px] flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors cursor-pointer select-none py-1 px-0.5 ${
              isMoreSectionActive
                ? 'text-[var(--text-main)] font-semibold'
                : 'text-[var(--text-sub)] hover:text-[var(--text-main)]'
            }`}
            id="mobile-tab-sections-btn"
          >
            <div
              className={`p-1 rounded-lg transition-all ${
                isMoreSectionActive
                  ? 'bg-[var(--card-subtle)] border border-[var(--card-border)] text-[var(--text-main)] shadow-2xs'
                  : 'text-[var(--text-muted)]'
              }`}
            >
              <LayoutGrid className="h-4 w-4" />
            </div>
            <span className="truncate max-w-[58px] leading-tight text-center">
              Разделы
            </span>
          </button>
        </div>
      </div>

      {/* ============================================================ */}
      {/* MOBILE SLIDE-UP MODAL/DRAWER FOR ALL SECTIONS                */}
      {/* ============================================================ */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex flex-col justify-end">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Modal Card */}
          <div className="relative bg-[var(--card-bg)] border-t border-[var(--card-border)] rounded-t-2xl p-4 pb-8 space-y-3 shadow-2xl max-h-[85vh] overflow-y-auto text-[var(--text-main)] z-10 animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between border-b border-[var(--card-border)] pb-3">
              <div>
                <h3 className="text-base font-semibold text-[var(--text-main)]">
                  Все разделы платформы
                </h3>
                <p className="text-xs text-[var(--text-sub)]">
                  Выберите необходимый рабочий раздел
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="min-h-[38px] min-w-[38px] flex items-center justify-center rounded-xl text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--card-subtle)] cursor-pointer transition-colors"
                aria-label="Закрыть меню разделов"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-1.5 pt-1">
              {tabs.map((tab) => {
                const Icon = TAB_ICONS[tab.id] || LayoutDashboard;
                const isActive = activeTab === tab.id;
                const isFocused = isRoleFocusedTab(tab.id);

                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => handleTabClick(tab.id)}
                    className={`min-h-[46px] w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border text-xs font-medium transition-all cursor-pointer ${
                      isActive
                        ? 'border-[var(--card-border)] bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 font-semibold shadow-2xs'
                        : 'border-[var(--card-border)] bg-[var(--card-subtle)] text-[var(--text-sub)] hover:text-[var(--text-main)] hover:bg-[var(--card-bg)]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-1.5 rounded-lg ${
                          isActive
                            ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900'
                            : 'bg-[var(--card-bg)] text-[var(--text-sub)] border border-[var(--card-border)]'
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="text-left">
                        <p className="font-semibold">{tab.label}</p>
                        {isFocused && (
                          <p className={`text-[10px] ${isActive ? 'text-slate-300 dark:text-slate-600' : 'text-[var(--text-muted)]'}`}>
                            Фокус роли {currentRoleDef.shortName}
                          </p>
                        )}
                      </div>
                    </div>

                    {tab.badge !== undefined && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          isActive
                            ? 'bg-red-600 text-white'
                            : 'bg-red-100 text-red-800 dark:bg-red-950/70 dark:text-red-200'
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
        </div>
      )}
    </>
  );
}
