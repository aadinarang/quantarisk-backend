import pytest
from unittest.mock import MagicMock
from app.services.alerts import (
    generate_alerts, get_alerts, mark_alert_read, mark_all_read
)


def make_snapshot(risk="MEDIUM", vol=0.02, drift=False, score=0.0):
    return {
        "symbol": "AAPL",
        "currentRisk": risk,
        "currentVolatility": vol,
        "driftFlag": drift,
        "driftScore": score,
    }


def test_generate_alerts_no_crash_on_empty_snapshot():
    db = MagicMock()
    generate_alerts(db, "AAPL", {}, None)


def test_generate_alerts_drift_detected():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    snap = make_snapshot(drift=True, score=0.8)
    prev = make_snapshot(drift=False)
    generate_alerts(db, "AAPL", snap, prev)
    db.add.assert_called()
    db.commit.assert_called()


def test_generate_alerts_drift_resolved():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    snap = make_snapshot(drift=False)
    prev = make_snapshot(drift=True)
    generate_alerts(db, "AAPL", snap, prev)
    db.add.assert_called()


def test_generate_alerts_risk_level_change():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    snap = make_snapshot(risk="HIGH")
    prev = make_snapshot(risk="LOW")
    generate_alerts(db, "AAPL", snap, prev)
    db.add.assert_called()


def test_generate_alerts_volatility_spike():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    snap = make_snapshot(vol=0.05)
    prev = make_snapshot(vol=0.02)
    generate_alerts(db, "AAPL", snap, prev)
    db.add.assert_called()


def test_generate_alerts_no_duplicate_if_existing():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    snap = make_snapshot(drift=True, score=0.8)
    prev = make_snapshot(drift=False)
    generate_alerts(db, "AAPL", snap, prev)
    db.add.assert_not_called()


def test_get_alerts_returns_list():
    db = MagicMock()
    mock_alert = MagicMock()
    mock_alert.id = "abc"
    mock_alert.timestamp.isoformat.return_value = "2025-01-01T00:00:00"
    mock_alert.symbol = "AAPL"
    mock_alert.type = "DRIFT_DETECTED"
    mock_alert.severity = "HIGH"
    mock_alert.message = "Test"
    mock_alert.detail = "Detail"
    mock_alert.read = False
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_alert]
    result = get_alerts(db)
    assert isinstance(result, list)
    assert result[0]["symbol"] == "AAPL"


def test_mark_alert_read_returns_false_if_not_found():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    result = mark_alert_read(db, "nonexistent")
    assert result == False


def test_mark_alert_read_returns_true_if_found():
    db = MagicMock()
    mock_alert = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = mock_alert
    result = mark_alert_read(db, "abc")
    assert result == True
    assert mock_alert.read == True


def test_mark_all_read_returns_count():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.update.return_value = 3
    result = mark_all_read(db)
    assert isinstance(result, int)

def test_get_alerts_for_user_returns_list():
    from app.services.alerts import get_alerts_for_user
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    result = get_alerts_for_user(db, user_id=1)
    assert isinstance(result, list)


def test_mark_alert_read_for_user_not_found():
    from app.services.alerts import mark_alert_read_for_user
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    result = mark_alert_read_for_user(db, user_id=1, alert_id="fake")
    assert result == False


def test_mark_all_read_for_user_returns_count():
    from app.services.alerts import mark_all_read_for_user
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    result = mark_all_read_for_user(db, user_id=1)
    assert isinstance(result, int)
