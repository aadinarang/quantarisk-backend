FROM python:3.11-slim

ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements-base.txt .
RUN pip install -r requirements-base.txt

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p data models && touch data/quantarisk.db
RUN chmod +x start.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["/bin/bash", "start.sh"]
