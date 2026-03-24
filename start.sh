#!/bin/bash
export PYTHONPATH=/app
python -m app.services.ingestion
uvicorn app.main:app --host 0.0.0.0 --port 8000
