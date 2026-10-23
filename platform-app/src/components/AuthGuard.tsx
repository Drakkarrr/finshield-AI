'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Spinner } from '@/components/ui';

const ROLE_RESTRICTED_ROUTES: Record<string, string[]> = {
  '/settings': ['admin', 'super_admin'],
  '/api-keys': ['admin', 'super_admin'],
  '/rules': ['analyst', 'admin', 'super_admin'],
};

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, isAuthenticated, router, pathname]);

  useEffect(() => {
    if (!isLoading && user) {
      const requiredRoles = ROLE_RESTRICTED_ROUTES[pathname];
      if (requiredRoles && !requiredRoles.includes(user.plan)) {
        router.push('/403');
      }
    }
  }, [isLoading, user, router, pathname]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-3" />
          <p className="text-sm text-ink-muted">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
