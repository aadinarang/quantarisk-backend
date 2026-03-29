#!/bin/bash

export PYTHONPATH=/app

echo '[start] Running data ingestion pipeline...'
python -m app.services.ingestion || echo '[start] Ingestion failed or skipped, continuing...'

echo '[start] Starting QuantaRisk API server...'
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
