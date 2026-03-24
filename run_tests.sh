#!/bin/bash
set -e
pip install -r requirements.txt -q
pytest tests/ -v --tb=short
