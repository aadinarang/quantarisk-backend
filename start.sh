#!/bin/bash
# Entrypoint: run ingestion pipeline then start the API server.
# Ingestion seeds symbols, fetches OHLCV, computes financial ratios,
# and writes data quality records before the server accepts requests.

set -e

export PYTHONPATH=/app

echo "[start] Running data ingestion pipeline..."
python -m app.services.ingestion

echo "[start] Starting QuantaRisk API server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
