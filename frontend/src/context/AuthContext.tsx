import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { UserProfile, AuthTokens } from '@/types';
import { apiClient, clearSectionData } from '@/api/client';
import { sessionKey } from '@/api/mode';

interface AuthContextType {
  user: UserProfile | null;
  tokens: AuthTokens | null;
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

export function AuthProvider({ children }: { children: ReactNode }) {
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
