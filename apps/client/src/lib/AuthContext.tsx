import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useContext, useState, type ReactNode } from 'react';

import { setToken } from '@/lib/auth';
import { api } from '@/lib/api';
import type { AuthUser } from '@/lib/types';

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  signIn: (token: string) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [hasToken, setHasToken] = useState(() => typeof window !== 'undefined');

  const me = useQuery({
    queryKey: ['auth-me'],
    queryFn: api.me,
    retry: false,
    enabled: hasToken,
  });

  const signIn = (token: string) => {
    setToken(token);
    setHasToken(true);
    void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
  };

  const signOut = () => {
    setToken(null);
    queryClient.setQueryData(['auth-me'], null);
    void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
  };

  const value: AuthContextValue = {
    user: me.isError ? null : (me.data ?? null),
    isLoading: hasToken && me.isLoading,
    signIn,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
