# FinShield AI - platform app (Next.js standalone, non-root)
# Built from the repository root: docker build -f platform-app/Dockerfile .

# Stage 1: dependencies (dev dependencies included: the build needs TypeScript, Tailwind, PostCSS)
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY platform-app/package.json platform-app/package-lock.json ./
RUN npm ci

# Stage 2: build
FROM node:22-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY platform-app/ .
ENV NEXT_TELEMETRY_DISABLED=1
# next.config.js rewrites /api/* to API_URL, and Next bakes rewrites in at build time.
ARG API_URL=http://backend:8091
ENV API_URL=${API_URL}
RUN npm run build

# Stage 3: runtime (standalone server only, no node_modules tree, no npm)
FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN groupadd --system finshield && useradd --system --gid finshield --no-create-home finshield
COPY --from=builder --chown=finshield:finshield /app/public ./public
COPY --from=builder --chown=finshield:finshield /app/.next/standalone ./
COPY --from=builder --chown=finshield:finshield /app/.next/static ./.next/static
USER finshield
EXPOSE 3000
# /login is public; `/` and every app page redirect when there is no session cookie.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/login', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
CMD ["node", "server.js"]
