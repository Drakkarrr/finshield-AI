# FinShield AI - Frontend Dockerfile (Hardened)
# Multi-stage build with Node 22, non-root user, standalone output

# Stage 1: Dependencies
FROM node:22-bookworm-slim AS deps

WORKDIR /app

# Install ALL dependencies (including dev) for the build
COPY platform-app/package.json platform-app/package-lock.json* ./
RUN npm ci

# Stage 2: Build
FROM node:22-bookworm-slim AS builder

WORKDIR /app

# Build argument for API URL (used by Next.js rewrites at build time)
ARG API_URL=http://backend:8091
ENV API_URL=${API_URL}

COPY --from=deps /app/node_modules ./node_modules
COPY platform-app/ .

# Disable telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Build Next.js application (standalone output)
RUN npm run build

# Stage 3: Runtime
FROM node:22-bookworm-slim AS runner

WORKDIR /app

# Security: Create non-root user
RUN groupadd -r finshield \
    && useradd -r -g finshield finshield \
    && chown -R finshield:finshield /app

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Copy built assets from builder
COPY --from=builder --chown=finshield:finshield /app/public ./public
COPY --from=builder --chown=finshield:finshield /app/.next/standalone ./
COPY --from=builder --chown=finshield:finshield /app/.next/static ./.next/static

# Expose port
EXPOSE 3000

# Set hostname
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Switch to non-root user
USER finshield

# Start the application
CMD ["node", "server.js"]
