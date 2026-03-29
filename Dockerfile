# QuantaRisk Backend — production Docker image
# Base: python:3.11-slim for a small, reproducible image

FROM python:3.11-slim

# Build arg injected by Jenkins: quantarisk-backend:BUILD_NUMBER
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

# Install system deps (curl needed for health check in compose)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create directories for DB and model mounts
RUN mkdir -p /data /models

# Make entrypoint executable
RUN chmod +x start.sh

EXPOSE 8000

# Health check — used by docker-compose and the Jenkins pipeline loop
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["/bin/bash", "start.sh"]
