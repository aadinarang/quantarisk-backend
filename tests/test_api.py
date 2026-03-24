import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_symbols():
    response = client.get("/api/symbols")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_risk_overview():
    response = client.get("/api/risk/overview")
    assert response.status_code == 200
    data = response.json()
    assert "totalSymbols" in data
    assert "highRiskCount" in data
    assert "mediumRiskCount" in data
    assert "lowRiskCount" in data
    assert "lastUpdated" in data


def test_get_risk_snapshot_valid_symbol():
    response = client.get("/api/risk/snapshot?symbol=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["currentRisk"] in ("LOW", "MEDIUM", "HIGH")
    assert data["currentVolatility"] > 0


def test_get_risk_snapshot_missing_symbol():
    response = client.get("/api/risk/snapshot")
    assert response.status_code == 422  # missing required param


def test_get_risk_history_valid_symbol():
    response = client.get("/api/risk/history?symbol=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert isinstance(data["points"], list)
    assert len(data["points"]) > 0


def test_get_drift_summary():
    response = client.get("/api/drift/summary")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)