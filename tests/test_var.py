"""Unit tests for VaR computation."""
import pandas as pd
import numpy as np
import pytest
from app.services.var import compute_var


def make_price_series(n: int = 260, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.01, n)
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * np.exp(r))
    return pd.Series(prices[1:])


def test_var_returns_dict():
    prices = make_price_series()
    result = compute_var(prices)
    assert isinstance(result, dict)


def test_var_has_required_keys():
    prices = make_price_series()
    result = compute_var(prices)
    assert "var95" in result
    assert "var99" in result
    assert "cvar95" in result


def test_var95_positive():
    prices = make_price_series()
    result = compute_var(prices)
    assert result["var95"] >= 0


def test_var99_gte_var95():
    """99% VaR should be larger (worse) than 95% VaR."""
    prices = make_price_series()
    result = compute_var(prices)
    assert result["var99"] >= result["var95"]


def test_cvar95_gte_var95():
    """CVaR (Expected Shortfall) >= VaR at same confidence level."""
    prices = make_price_series()
    result = compute_var(prices)
    assert result["cvar95"] >= result["var95"]


def test_var_short_series_returns_zeros():
    """Too short a series should return zeros gracefully."""
    prices = pd.Series([100.0, 101.0, 99.0])
    result = compute_var(prices)
    assert result["var95"] == 0.0
    assert result["var99"] == 0.0


def test_var_values_are_floats():
    prices = make_price_series()
    result = compute_var(prices)
    for v in result.values():
        assert isinstance(v, float)


def test_var_reasonable_magnitude():
    """For a 1% daily vol stock, 95% VaR should be roughly 1.5-2.0%."""
    prices = make_price_series()
    result = compute_var(prices)
    # parametric: z95 * sigma ~ 1.645 * 0.01 = 0.0165
    assert 0.005 < result["var95"] < 0.10
