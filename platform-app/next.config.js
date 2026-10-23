/** @type {import('next').NextConfig} */

// Production needs 'unsafe-inline' for Next's inline bootstrap scripts (no nonce middleware);
// 'unsafe-eval' only in `next dev`, where React Refresh needs it.
const isDev = process.env.NODE_ENV !== 'production';
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join('; ');

const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  async headers() {
    return [
      {
        // Pages only: /api/* is the backend's own response (its Swagger UI loads its own assets).
        source: '/((?!api/).*)',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
        ],
      },
    ];
  },
  async rewrites() {
    // Evaluated at BUILD time and baked into the output: set API_URL before `next build`
    // (the Dockerfile does), not only at runtime.
    const apiUrl = process.env.API_URL || 'http://localhost:8091';
    return [{ source: '/api/:path*', destination: `${apiUrl}/api/:path*` }];
  },
};

module.exports = nextConfig;
