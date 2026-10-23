'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingState, buttonClasses } from '@/components/ui';
import { canCall, requiredRole, Route } from '@/lib/permissions';

/**
 * Client half of route protection: no profile → login with a return path. The proxy already did
 * this for a missing cookie; this covers an expired or revoked one.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      const back = window.location.pathname + window.location.search;
      router.replace(`/login?redirect=${encodeURIComponent(back)}`);
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingState label={isLoading ? 'Checking your session…' : 'Redirecting to sign in…'} />
      </div>
    );
  }
  return <>{children}</>;
}

/** When the page's API route needs a higher role, show a 403 state (the API would refuse anyway). */
export function RoleGate({ requires, children }: { requires?: Route; children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  if (!requires || canCall(user?.role, requires)) return <>{children}</>;
  return (
    <div className="py-20 text-center" role="alert">
      <p className="text-5xl font-bold text-danger-fg mb-3">403</p>
      <h1 className="text-xl font-semibold text-ink mb-2">You don&apos;t have access to this page</h1>
      <p className="text-sm text-ink-muted mb-6">
        <span className="font-mono">{pathname}</span> needs the <strong>{requiredRole(requires)}</strong> role; you are
        signed in as <strong>{user?.role}</strong>. Ask an admin of your organisation if you need it.
      </p>
      <Link href="/dashboard" className={buttonClasses('primary')}>Go to dashboard</Link>
    </div>
  );
}
