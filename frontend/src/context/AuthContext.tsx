import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { UserProfile, AuthTokens } from '@/types';
import { apiClient, clearSectionData } from '@/api/client';
import { CompanyRequestError, companyAuth, companyClientEnabled, resetCompanySession, type CompanyProfile } from '@/api/companySession';
import { sessionKey } from '@/api/mode';

interface AuthContextType {
  user: UserProfile | null;
  tokens: AuthTokens | null;
  companyProfile?: CompanyProfile | null;
  setCompanyProfile?: (profile: CompanyProfile) => void;
  bootstrapError?: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { company_name: string; inn?: string; full_name: string; email: string; password: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
});

function LegacyAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(() => {
    const saved = localStorage.getItem(sessionKey);
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (tokens?.access_token) {
      apiClient.getProfile()
        .then((profile) => setUser(profile))
        .catch(() => {
          clearSectionData();
          setTokens(null);
          localStorage.removeItem(sessionKey);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [tokens?.access_token]);

  const login = async (email: string, password: string) => {
    const response = await apiClient.login({ email, password });
    setTokens(response);
    localStorage.setItem(sessionKey, JSON.stringify(response));
  };

  const register = async (data: { company_name: string; inn?: string; full_name: string; email: string; password: string }) => {
    const response = await apiClient.register(data);
    setTokens(response);
    localStorage.setItem(sessionKey, JSON.stringify(response));
  };

  const logout = () => {
    clearSectionData();
    setUser(null);
    setTokens(null);
    localStorage.removeItem(sessionKey);
  };

  return (
    <AuthContext.Provider value={{
      user,
      tokens,
      isAuthenticated: !!tokens?.access_token,
      isLoading,
      login,
      register,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

function CompanyAuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [bootstrapError, setBootstrapError] = useState(false);

  useEffect(() => {
    localStorage.removeItem(sessionKey);
    let active = true;
    const clear = () => {
      resetCompanySession();
      clearSectionData();
      setProfile(null);
    };
    window.addEventListener('seh-company-session-ended', clear);
    void companyAuth.profile()
      .then(value => { if (active) setProfile(value); })
      .catch(error => {
        if (active && !(error instanceof DOMException && error.name === 'AbortError')
          && !(error instanceof CompanyRequestError && (error.status === 401 || error.code === 'COMPANY_PAUSED'))) {
          setBootstrapError(true);
        }
      })
      .finally(() => { if (active) setIsLoading(false); });
    return () => {
      active = false;
      window.removeEventListener('seh-company-session-ended', clear);
    };
  }, []);

  function setCompanyProfile(value: CompanyProfile) {
    resetCompanySession();
    clearSectionData();
    setProfile(value);
  }

  async function logout() {
    await companyAuth.logout();
    resetCompanySession();
    clearSectionData();
    setProfile(null);
  }

  return (
    <AuthContext.Provider value={{
      user: profile,
      tokens: null,
      isAuthenticated: !!profile,
      isLoading,
      companyProfile: profile,
      bootstrapError,
      setCompanyProfile,
      login: async () => { throw new Error('Используйте вход по коду компании.'); },
      register: async () => { throw new Error('Доступ выдаётся по приглашению.'); },
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return companyClientEnabled
    ? <CompanyAuthProvider>{children}</CompanyAuthProvider>
    : <LegacyAuthProvider>{children}</LegacyAuthProvider>;
}