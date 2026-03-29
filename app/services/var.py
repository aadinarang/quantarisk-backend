"""Parametric Value-at-Risk and Conditional VaR (Expected Shortfall)."""
import numpy as np
import pandas as pd
from scipy.stats import norm


def compute_var(price_series: pd.Series, window: int = 252) -> dict:
    """
    Compute 1-day parametric VaR at 95% and 99% confidence,
    plus CVaR (Expected Shortfall) at 95%.

    Uses the variance-covariance method under a normal distribution.

    VaR_α = -(μ + z_α × σ)
    CVaR_95 = -(μ - σ × φ(z_0.05) / 0.05)

    where μ and σ are from the trailing `window` log returns.

    Returns a dict with var95, var99, cvar95 as positive decimals
    (e.g. 0.021 means the max expected daily loss is 2.1%).
    """
    if len(price_series) < 22:
        return {"var95": 0.0, "var99": 0.0, "cvar95": 0.0}

    prices = price_series.dropna()
    if len(prices) > window:
        prices = prices.iloc[-window:]

    log_returns = np.log(prices / prices.shift(1)).dropna()
    if len(log_returns) < 20:
        return {"var95": 0.0, "var99": 0.0, "cvar95": 0.0}

    mu    = float(log_returns.mean())
    sigma = float(log_returns.std())

    if sigma <= 0:
        return {"var95": 0.0, "var99": 0.0, "cvar95": 0.0}

    # Normal quantiles
    z95 = norm.ppf(0.05)  # -1.6449
    z99 = norm.ppf(0.01)  # -2.3263

    var95  = -(mu + z95 * sigma)
    var99  = -(mu + z99 * sigma)

    # CVaR / Expected Shortfall at 95%: E[L | L > VaR_95]
    phi_z05 = norm.pdf(z95)          # standard normal PDF at z95
    cvar95  = -(mu - sigma * phi_z05 / 0.05)

    # Clamp to reasonable positive values
    var95  = max(0.0, round(var95,  6))
    var99  = max(0.0, round(var99,  6))
    cvar95 = max(0.0, round(cvar95, 6))

    return {"var95": var95, "var99": var99, "cvar95": cvar95}
