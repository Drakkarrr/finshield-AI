'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { api, AuthUser, UserProfile, ApiError } from '@/lib/api';

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (data: { firstName: string; lastName: string; email: string; company: string; password: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check if we have a token and fetch user profile
  useEffect(() => {
    const token = api.getToken();
    if (token) {
      api.me()
        .then(profile => {
          setUser(profile);
        })
        .catch(() => {
          // Token expired or invalid
          api.clearToken();
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login({ email, password });
    api.setToken(response.access_token);
    // Fetch full profile
    const profile = await api.me();
    setUser(profile);
  }, []);

  const signup = useCallback(async (data: {
    firstName: string;
    lastName: string;
    email: string;
    company: string;
    password: string;
  }) => {
    const response = await api.register({
      email: data.email,
      password: data.password,
      first_name: data.firstName,
      last_name: data.lastName,
      company: data.company,
    });
    api.setToken(response.access_token);
    // Fetch full profile
    const profile = await api.me();
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
    window.location.href = '/login';
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const profile = await api.me();
      setUser(profile);
    } catch {
      // Token expired
      api.clearToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      signup,
      logout,
      refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
