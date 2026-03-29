"""Unit tests for OHLCV data quality validation."""
import pandas as pd
import pytest
from app.services.data_quality import (
    validate_ohlcv,
    count_null_values,
    count_date_gaps,
    count_price_range_violations,
)


def make_clean_df(n: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="B")  # business days
    return pd.DataFrame({
        "date":   dates,
        "open":   [100 + i for i in range(n)],
        "high":   [105 + i for i in range(n)],
        "low":    [95  + i for i in range(n)],
        "close":  [102 + i for i in range(n)],
        "volume": [1_000_000] * n,
    })


# ── validate_ohlcv ────────────────────────────────────────────────
def test_valid_df_no_errors():
    assert validate_ohlcv(make_clean_df()) == []


def test_missing_column_raises_error():
    df = make_clean_df().drop(columns=["volume"])
    errors = validate_ohlcv(df)
    assert any("Missing column" in e for e in errors)


def test_negative_close_raises_error():
    df = make_clean_df()
    df.loc[0, "close"] = -5.0
    errors = validate_ohlcv(df)
    assert any("positive" in e for e in errors)


def test_negative_volume_raises_error():
    df = make_clean_df()
    df.loc[0, "volume"] = -1
    errors = validate_ohlcv(df)
    assert any("volume" in e for e in errors)


def test_null_date_raises_error():
    df = make_clean_df()
    df.loc[0, "date"] = None
    errors = validate_ohlcv(df)
    assert any("null" in e for e in errors)


# ── count_null_values ────────────────────────────────────────────
def test_no_nulls_in_clean_df():
    assert count_null_values(make_clean_df()) == 0


def test_null_close_counted():
    df = make_clean_df()
    df.loc[2, "close"] = float("nan")
    assert count_null_values(df) == 1


# ── count_date_gaps ──────────────────────────────────────────────
def test_no_gaps_in_business_day_series():
    assert count_date_gaps(make_clean_df()) == 0


def test_large_gap_detected():
    dates = pd.to_datetime(["2025-01-01", "2025-01-20"])  # 19-day gap
    df = pd.DataFrame({"date": dates})
    assert count_date_gaps(df) == 1


# ── count_price_range_violations ─────────────────────────────────
def test_no_violations_in_clean_df():
    assert count_price_range_violations(make_clean_df()) == 0


def test_high_below_low_is_violation():
    df = make_clean_df()
    df.loc[0, "high"] = 90.0   # below low of 95
    assert count_price_range_violations(df) > 0

def test_compute_data_quality_no_records():
    from unittest.mock import MagicMock
    from app.services.data_quality import compute_data_quality
    db = MagicMock()
    db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []
    result = compute_data_quality(db, "AAPL")
    assert result["symbol"] == "AAPL"
    assert result["totalRecords"] == 0
    assert result["status"] == "FAIL"
    assert result["completeness"] == 0.0


def test_compute_data_quality_with_records():
    import datetime
    from unittest.mock import MagicMock
    from app.services.data_quality import compute_data_quality
    db = MagicMock()
    records = []
    base = datetime.date(2024, 1, 1)
    for i in range(252):
        r = MagicMock()
        r.date = base + datetime.timedelta(days=i)
        r.open = 100.0 + i
        r.high = 105.0 + i
        r.low = 95.0 + i
        r.close = 102.0 + i
        r.volume = 1_000_000
        records.append(r)
    db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = records
    result = compute_data_quality(db, "AAPL")
    assert result["symbol"] == "AAPL"
    assert result["totalRecords"] == 252
    assert result["status"] in ("PASS", "WARN", "FAIL")
    assert 0.0 <= result["completeness"] <= 1.0


def test_compute_data_quality_status_pass():
    import datetime
    from unittest.mock import MagicMock
    from app.services.data_quality import compute_data_quality
    db = MagicMock()
    records = []
    base = datetime.date(2024, 1, 1)
    price = 100.0
    for i in range(252):
        r = MagicMock()
        r.date = base + datetime.timedelta(days=i)
        r.open = price
        r.high = price + 1
        r.low = price - 1
        r.close = price
        r.volume = 1_000_000
        records.append(r)
        price += 0.1
    db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = records
    result = compute_data_quality(db, "AAPL")
    assert result["status"] == "PASS"
