FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Layer 1 — heavy deps (torch, numpy, scipy etc) — only rebuilds if requirements-base.txt changes
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Layer 2 — light deps — rebuilds when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data models
RUN chmod +x start.sh
