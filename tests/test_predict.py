"""Unit tests for the price forecast service (PyTorch LSTM path + fallback)."""

import pandas as pd
import numpy as np

from app.services.predict import generate_forecast, _math_forecast


def make_ohlcv_df(n: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    prices = [100.0]
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    for _ in range(n):
        daily_ret = rng.normal(0, 0.01)
        close = prices[-1] * np.exp(daily_ret)
        open_ = close * (1 + rng.normal(0, 0.002))
        high = max(open_, close) * (1 + abs(rng.normal(0, 0.003)))
        low = min(open_, close) * (1 - abs(rng.normal(0, 0.003)))
        volume = max(1000, int(rng.normal(1_000_000, 100_000)))

        prices.append(close)
        opens.append(open_)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        volumes.append(volume)

    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=dates)


def test_generate_forecast_returns_dict():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=10)
    assert isinstance(result, dict)


def test_forecast_has_required_keys():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("TEST", prices_df, horizon=10)
    for key in ("symbol", "forecastDates", "forecastPrices", "upperBand", "lowerBand", "modelVersion"):
        assert key in result


def test_forecast_horizon_length():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=10)
    assert len(result["forecastPrices"]) == 10
    assert len(result["upperBand"]) == 10
    assert len(result["lowerBand"]) == 10
    assert len(result["forecastDates"]) == 10


def test_forecast_dates_are_strings():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=5)
    for d in result["forecastDates"]:
        assert isinstance(d, str)
        assert len(d) == 10  # YYYY-MM-DD


def test_upper_band_above_lower():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=10)
    for lo, hi in zip(result["lowerBand"], result["upperBand"]):
        assert hi >= lo


def test_forecast_prices_positive():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=10)
    for p in result["forecastPrices"]:
        assert p > 0


def test_math_forecast_short_series():
    prices_df = make_ohlcv_df(10)
    result = _math_forecast(prices_df, horizon=5)
    assert len(result["forecastPrices"]) == 5


def test_model_version_set():
    prices_df = make_ohlcv_df(120)
    result = generate_forecast("AAPL", prices_df, horizon=10)
    assert result["modelVersion"] in ("math-v1", "lstm-v1")