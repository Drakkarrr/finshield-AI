# FinShield AI - Backend Dockerfile (build context: repo root). Hardened (S6.3):
# multi-stage (no compiler in the runtime image), pruned site-packages, non-root user.

# --- Build stage: compiler available, dependencies installed into a virtualenv -------------------
FROM python:3.11-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY backend/requirements.txt backend/requirements-rag.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-rag.txt \
    # Test suites and C++ headers are never used at runtime.
    && find /opt/venv/lib/python3.11/site-packages -type d -name tests -prune -exec rm -rf {} + \
    && rm -rf /opt/venv/lib/python3.11/site-packages/torch/include \
    && pip uninstall -y pip setuptools wheel

# Bake the embedding model into the image; the runtime never downloads it (ruling D4).
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"

# --- Runtime stage -----------------------------------------------------------------------------
FROM python:3.11-slim

RUN groupadd --system --gid 10001 finshield \
    && useradd --system --uid 10001 --gid finshield --home-dir /app --shell /usr/sbin/nologin finshield

COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/hf /opt/hf
ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/hf HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY --chown=finshield:finshield backend/ ./
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh \
    && mkdir -p /app/data && chown finshield:finshield /app/data

USER finshield

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8091/api/health/live')" || exit 1

# Migrate to head, bootstrap reference data, then run the application. Behind a TLS proxy set
# FORWARDED_ALLOW_IPS to the proxy's address so X-Forwarded-Proto is trusted (S6.2).
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091", "--proxy-headers"]
