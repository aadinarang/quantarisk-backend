import pytest
from unittest.mock import MagicMock, patch
from app.services.snapshot_jobs import refresh_all_snapshots


def make_mock_db(symbols=None, with_previous=False):
    symbols = symbols or ["AAPL", "MSFT"]
    db = MagicMock()

    sym_objects = []
    for s in symbols:
        sym = MagicMock()
        sym.symbol = s
        sym_objects.append(sym)

    db.query.return_value.all.return_value = sym_objects

    prev_row = None
    if with_previous:
        prev_row = MagicMock()
        prev_row.symbol = "AAPL"
        prev_row.risk_level = "LOW"
        prev_row.volatility = 0.01
        prev_row.drift_flag = False
        prev_row.drift_score = 0.0
        prev_row.vol_source = "rolling"

    db.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = prev_row
    return db


def test_refresh_all_snapshots_runs_without_error():
    db = make_mock_db()
    mock_snapshot = {
        "symbol": "AAPL",
        "currentRisk": "LOW",
        "currentVolatility": 0.01,
        "driftFlag": False,
        "driftScore": 0.0,
        "volSource": "rolling",
    }
    with patch("app.services.snapshot_jobs.get_snapshot", return_value=mock_snapshot), \
         patch("app.services.snapshot_jobs.generate_alerts"):
        refresh_all_snapshots(db)
        db.add.assert_called()
        db.commit.assert_called()


def test_refresh_all_snapshots_skips_empty_snapshot():
    db = make_mock_db()
    with patch("app.services.snapshot_jobs.get_snapshot", return_value={}), \
         patch("app.services.snapshot_jobs.generate_alerts") as mock_alerts:
        refresh_all_snapshots(db)
        mock_alerts.assert_not_called()


def test_refresh_all_snapshots_with_previous_snapshot():
    db = make_mock_db(with_previous=True)
    mock_snapshot = {
        "symbol": "AAPL",
        "currentRisk": "HIGH",
        "currentVolatility": 0.05,
        "driftFlag": True,
        "driftScore": 0.8,
        "volSource": "garch",
    }
    with patch("app.services.snapshot_jobs.get_snapshot", return_value=mock_snapshot), \
         patch("app.services.snapshot_jobs.generate_alerts") as mock_alerts:
        refresh_all_snapshots(db)
        mock_alerts.assert_called()


def test_refresh_all_snapshots_empty_symbol_list():
    db = MagicMock()
    db.query.return_value.all.return_value = []
    with patch("app.services.snapshot_jobs.get_snapshot") as mock_snap, \
         patch("app.services.snapshot_jobs.generate_alerts"):
        refresh_all_snapshots(db)
        mock_snap.assert_not_called()
