import { createContext, useContext, useState, type ReactNode } from 'react';
import {
  type EnterpriseRoleId,
  type EnterpriseRoleDefinition,
  ENTERPRISE_ROLES,
} from '@/types/roles';

interface RoleContextType {
  activeRole: EnterpriseRoleId;
  setActiveRole: (role: EnterpriseRoleId) => void;
  currentRoleDef: EnterpriseRoleDefinition;
  roles: EnterpriseRoleDefinition[];
  isRoleFocusedTab: (tabId: string) => boolean;
}

const defaultRoleDef = ENTERPRISE_ROLES[0];

const RoleContext = createContext<RoleContextType>({
  activeRole: 'ceo',
  setActiveRole: () => {},
  currentRoleDef: defaultRoleDef,
  roles: ENTERPRISE_ROLES,
  isRoleFocusedTab: () => true,
});

const ROLE_STORAGE_KEY = 'seh-active-role';

export function RoleProvider({ children }: { children: ReactNode }) {
  const [activeRole, setActiveRoleState] = useState<EnterpriseRoleId>(() => {
    const saved = localStorage.getItem(ROLE_STORAGE_KEY) as EnterpriseRoleId | null;
    if (saved && ENTERPRISE_ROLES.some((r) => r.id === saved)) {
      return saved;
    }
    return 'ceo';
  });

  const setActiveRole = (role: EnterpriseRoleId) => {
    setActiveRoleState(role);
    localStorage.setItem(ROLE_STORAGE_KEY, role);
  };

  const currentRoleDef =
    ENTERPRISE_ROLES.find((r) => r.id === activeRole) || defaultRoleDef;

  const isRoleFocusedTab = (tabId: string): boolean => {
    return currentRoleDef.focusTabs.includes(tabId);
  };

  return (
    <RoleContext.Provider
      value={{
        activeRole,
        setActiveRole,
        currentRoleDef,
        roles: ENTERPRISE_ROLES,
        isRoleFocusedTab,
      }}
    >
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  return useContext(RoleContext);
}
