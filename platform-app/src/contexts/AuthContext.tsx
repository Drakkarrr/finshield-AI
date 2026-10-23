'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { api, UserProfile } from '@/lib/api';
import { canCall, Route } from '@/lib/permissions';

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: { firstName: string; lastName: string; email: string; company: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Session state is "does GET /api/auth/me succeed": the session itself is an httpOnly cookie the
 * browser sends automatically and scripts cannot read.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api.login({ email, password });
    setUser(await api.me());
  }, []);

  const signup = useCallback(async (data: { firstName: string; lastName: string; email: string; company: string; password: string }) => {
    await api.register({
      email: data.email,
      password: data.password,
      first_name: data.firstName,
      last_name: data.lastName,
      company: data.company,
    });
    setUser(await api.me());
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      // A full page load, not router.push: it drops every cached response of the previous user.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign('/login');
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, signup, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

/** `can(['DELETE', '/api/v1/cases/{case_id}'])` — whether the signed-in role may call that route. */
export function useCan() {
  const { user } = useAuth();
  return useCallback((route: Route) => canCall(user?.role, route), [user?.role]);
}
