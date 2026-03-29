#!/bin/bash
# Run the full test suite locally (without Docker).
# Requires: pip install -r requirements.txt

set -e
export PYTHONPATH=$(pwd)
export DATABASE_URL=sqlite:///./test.db

echo "Running QuantaRisk test suite..."
pytest tests/ -v \
    --tb=short \
    --cov=app \
    --cov-report=term-missing \
    --cov-fail-under=80

echo "All tests passed."
