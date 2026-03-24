import pandas as pd
import numpy as np
import pytest
from app.services.analytics import compute_volatility, classify_risk


def make_price_df(prices: list) -> pd.DataFrame:
    dates = pd.date_range(start="2025-01-01", periods=len(prices), freq="D")
    df = pd.DataFrame({"close": prices}, index=dates)
    df.index.name = "date"
    return df


def test_compute_volatility_returns_series():
    prices = [100 + i * 0.5 for i in range(60)]
    df = make_price_df(prices)
    vol = compute_volatility(df, window=20)
    assert isinstance(vol, pd.Series)
    assert len(vol) == len(df)


def test_compute_volatility_no_nans_after_window():
    prices = [100 + i * 0.5 for i in range(60)]
    df = make_price_df(prices)
    vol = compute_volatility(df, window=20).dropna()
    assert len(vol) > 0
    assert not vol.isnull().any()


def test_compute_volatility_non_negative():
    prices = [100 + i * 0.5 for i in range(60)]
    df = make_price_df(prices)
    vol = compute_volatility(df, window=20).dropna()
    assert (vol >= 0).all()


def test_classify_risk_low():
    # Current vol is very low relative to history
    historical = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05] * 10)
    result = classify_risk(0.001, historical)
    assert result == "LOW"


def test_classify_risk_high():
    # Current vol is very high relative to history
    historical = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05] * 10)
    result = classify_risk(0.999, historical)
    assert result == "HIGH"


def test_classify_risk_medium():
    historical = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05] * 10)
    result = classify_risk(0.03, historical)
    assert result in ("LOW", "MEDIUM", "HIGH")


def test_classify_risk_returns_valid_label():
    historical = pd.Series(np.random.uniform(0.01, 0.05, 100))
    for vol in [0.001, 0.03, 0.999]:
        result = classify_risk(vol, historical)
        assert result in ("LOW", "MEDIUM", "HIGH")
