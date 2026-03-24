import pandas as pd
import numpy as np
from app.services.garch import fit_garch_forecast, get_garch_volatility_series


def make_returns(n: int = 300, seed: int = 42) -> pd.Series:
    """Generate synthetic log returns for testing."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, 0.01, n))


def test_garch_forecast_returns_float_with_enough_data():
    returns = make_returns(300)
    result = fit_garch_forecast(returns)
    assert result is not None
    assert isinstance(result, float)


def test_garch_forecast_returns_none_with_insufficient_data():
    returns = make_returns(100)  # less than 252
    result = fit_garch_forecast(returns)
    assert result is None


def test_garch_forecast_is_positive():
    returns = make_returns(300)
    result = fit_garch_forecast(returns)
    if result is not None:
        assert result > 0


def test_garch_vol_series_returns_series():
    returns = make_returns(300)
    series = get_garch_volatility_series(returns)
    assert isinstance(series, pd.Series)


def test_garch_vol_series_non_negative():
    returns = make_returns(300)
    series = get_garch_volatility_series(returns)
    if not series.empty:
        assert (series >= 0).all()


def test_garch_vol_series_empty_on_short_data():
    returns = make_returns(100)
    series = get_garch_volatility_series(returns)
    assert series.empty
