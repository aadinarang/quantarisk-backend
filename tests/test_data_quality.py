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
