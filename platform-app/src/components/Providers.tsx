'use client';

import { ReactNode } from 'react';
import { SWRConfig } from 'swr';
import { AuthProvider } from '@/contexts/AuthContext';

// Errors are shown, not retried: a 403/404/422 will not change by asking again.
const swrConfig = { revalidateOnFocus: false, shouldRetryOnError: false, keepPreviousData: true };

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={swrConfig}>
      <AuthProvider>{children}</AuthProvider>
    </SWRConfig>
  );
}
