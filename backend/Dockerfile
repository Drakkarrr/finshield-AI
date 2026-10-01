# FinShield AI - Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Expose port
EXPOSE 8091

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091"]
