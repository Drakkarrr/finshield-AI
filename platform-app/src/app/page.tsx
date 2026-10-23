import { redirect } from 'next/navigation';

// src/proxy.ts sends `/` to /dashboard or /login before this renders; this is the fallback.
export default function RootPage() {
  redirect('/dashboard');
}
