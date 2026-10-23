import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Set httpOnly by the backend on login/register (ruling D11); scripts cannot read it, the server can.
const SESSION_COOKIE = 'finshield_session';
const PUBLIC_PAGES = ['/login', '/signup'];

/**
 * Optimistic route protection (S5.5): a page request without a session cookie goes to the login
 * page with a return path. The cookie is not validated here — the API validates it on every call,
 * an invalid or expired one ends in the same login redirect client-side, and role gating happens
 * in the UI against GET /api/auth/me.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return NextResponse.next();

  const hasSession = request.cookies.has(SESSION_COOKIE);
  if (pathname === '/') {
    return NextResponse.redirect(new URL(hasSession ? '/dashboard' : '/login', request.url));
  }
  if (!hasSession) {
    const login = new URL('/login', request.url);
    login.searchParams.set('redirect', pathname + search);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // Pages only: not the /api proxy to the backend, Next internals or static files.
  matcher: ['/((?!api/|_next/|favicon.ico|.*\\..*).*)'],
};
