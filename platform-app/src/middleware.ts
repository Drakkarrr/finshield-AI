import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that require authentication
const AUTHENTICATED_ROUTES = [
  '/dashboard',
  '/transactions',
  '/cases',
  '/rules',
  '/settings',
  '/api-keys',
  '/reports',
  '/filings',
  '/docs',
];

// Routes that require specific roles
const ROLE_RESTRICTED_ROUTES: Record<string, string[]> = {
  '/settings': ['admin', 'super_admin'],
  '/api-keys': ['admin', 'super_admin'],
  '/rules': ['analyst', 'admin', 'super_admin'],
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip middleware for static files, API routes, and public routes
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/login') ||
    pathname.startsWith('/signup') ||
    pathname === '/' ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Check if route requires authentication
  const requiresAuth = AUTHENTICATED_ROUTES.some((route) => pathname.startsWith(route));

  if (requiresAuth) {
    // Check for auth token in localStorage (client-side) or cookie
    // Since middleware runs on server, we check for a session cookie
    const token = request.cookies.get('finshield_token')?.value;

    if (!token) {
      // Redirect to login with return URL
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }

    // Check role-based access
    const requiredRoles = ROLE_RESTRICTED_ROUTES[pathname];
    if (requiredRoles) {
      // Decode token to get user role (simplified - in production, validate JWT)
      const userRole = request.cookies.get('user_role')?.value;

      if (!userRole || !requiredRoles.includes(userRole)) {
        // Return 403 Forbidden
        return new NextResponse('Forbidden - Insufficient permissions', { status: 403 });
      }
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder assets
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)',
  ],
};
