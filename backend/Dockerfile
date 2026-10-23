# FinShield AI - Backend Dockerfile (build context: repo root)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt backend/requirements-rag.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-rag.txt

# Bake the embedding model into the image; the runtime never downloads it (ruling D4).
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# Copy backend code
COPY backend/ ./
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# Expose port
EXPOSE 8091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8091/api/health/live')" || exit 1

# Migrate to head, bootstrap reference data, then run the application
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
