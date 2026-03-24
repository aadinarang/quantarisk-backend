import pandas as pd
import pytest


def validate_ohlcv(df: pd.DataFrame) -> list:
    errors = []
    required = ["date", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing column: {col}")
    if "close" in df.columns:
        if (df["close"] <= 0).any():
            errors.append("close prices must be positive")
    if "volume" in df.columns:
        if (df["volume"] < 0).any():
            errors.append("volume must be non-negative")
    if "date" in df.columns:
        if df["date"].isnull().any():
            errors.append("date column has nulls")
    return errors


def test_valid_data_passes():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=5),
        "open": [100, 101, 102, 103, 104],
        "high": [105, 106, 107, 108, 109],
        "low":  [99, 100, 101, 102, 103],
        "close": [101, 102, 103, 104, 105],
        "volume": [1000, 2000, 3000, 4000, 5000],
    })
    errors = validate_ohlcv(df)
    assert errors == []


def test_missing_column_fails():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=3),
        "close": [100, 101, 102],
    })
    errors = validate_ohlcv(df)
    assert any("Missing column" in e for e in errors)


def test_negative_price_fails():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=3),
        "open": [100, 101, 102],
        "high": [105, 106, 107],
        "low":  [99, 100, 101],
        "close": [-1, 102, 103],
        "volume": [1000, 2000, 3000],
    })
    errors = validate_ohlcv(df)
    assert any("positive" in e for e in errors)


def test_negative_volume_fails():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=3),
        "open": [100, 101, 102],
        "high": [105, 106, 107],
        "low":  [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [-1, 2000, 3000],
    })
    errors = validate_ohlcv(df)
    assert any("volume" in e for e in errors)


def test_null_date_fails():
    df = pd.DataFrame({
        "date": [None, pd.Timestamp("2025-01-02"), pd.Timestamp("2025-01-03")],
        "open": [100, 101, 102],
        "high": [105, 106, 107],
        "low":  [99, 100, 101],
        "close": [101, 102, 103],
        "volume": [1000, 2000, 3000],
    })
    errors = validate_ohlcv(df)
    assert any("null" in e for e in errors)
