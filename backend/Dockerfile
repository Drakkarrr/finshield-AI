# FinShield AI - Backend Dockerfile (Hardened)
# Multi-stage build with non-root user

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r finshield \
    && useradd -r -g finshield -G www-data finshield \
    && chown -R finshield:finshield /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=finshield:finshield backend/ ./

# Make entrypoint executable
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# Expose port
EXPOSE 8091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8091/api/health/live || exit 1

# Switch to non-root user
USER finshield

# Migrate to head, then run the application
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
