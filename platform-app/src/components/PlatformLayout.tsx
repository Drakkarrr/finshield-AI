'use client';

import React, { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import AuthGuard, { RoleGate } from './AuthGuard';
import { pageRequirement } from '@/lib/routes';

export default function PlatformLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <AuthGuard>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-modal focus:bg-surface focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-dropdown">
        Skip to content
      </a>
      <div className="flex min-h-screen bg-bg">
        <Sidebar />
        <div className="flex-1 ml-sidebar flex flex-col min-w-0">
          <Topbar />
          <main id="main" className="flex-1 p-6 overflow-auto">
            <RoleGate requires={pageRequirement(pathname)}>{children}</RoleGate>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
