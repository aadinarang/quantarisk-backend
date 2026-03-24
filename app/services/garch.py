import pandas as pd
import numpy as np
from arch import arch_model


def fit_garch_forecast(returns: pd.Series) -> float | None:
    """
    Fit a GARCH(1,1) model on log returns and forecast
    next-day volatility. Returns the forecasted volatility
    as a float, or None if fitting fails.
    
    Parameters:
        returns: pd.Series of daily log returns
    
    Returns:
        float: forecasted next-day volatility (annualised optional)
        None: if model fails to converge or not enough data
    """
    # Need at least 252 trading days for a reliable fit
    if len(returns.dropna()) < 252:
        return None

    try:
        # Scale returns to percentage (arch library works better this way)
        scaled = returns.dropna() * 100

        # Fit GARCH(1,1) - the standard model in finance
        model = arch_model(
            scaled,
            vol="Garch",
            p=1,
            q=1,
            mean="Zero",      # assume zero mean for returns (standard)
            dist="normal"
        )

        result = model.fit(
            disp="off",       # suppress fitting output
            show_warning=False
        )

        # Forecast 1 step ahead
        forecast = result.forecast(horizon=1, reindex=False)

        # Extract forecasted variance, take sqrt for volatility
        # Divide by 100 to undo our earlier scaling
        forecasted_variance = forecast.variance.iloc[-1, 0]
        forecasted_vol = (forecasted_variance ** 0.5) / 100

        return float(forecasted_vol)

    except Exception:
        # GARCH can fail on unusual series (flat, spiky, etc.)
        # Return None and let caller fall back to rolling std
        return None


def get_garch_volatility_series(returns: pd.Series, window: int = 252) -> pd.Series:
    """
    Compute a rolling GARCH-fitted conditional volatility series.
    Used for building historical volatility context and drift detection.
    
    This is different from fit_garch_forecast which only returns 
    the next-day forecast. This returns the full conditional 
    volatility series from the fitted model.
    
    Parameters:
        returns: pd.Series of daily log returns
        window: minimum number of observations required
    
    Returns:
        pd.Series of conditional volatility values (same index as returns)
    """
    if len(returns.dropna()) < window:
        return pd.Series(dtype=float)

    try:
        scaled = returns.dropna() * 100

        model = arch_model(
            scaled,
            vol="Garch",
            p=1,
            q=1,
            mean="Zero",
            dist="normal"
        )

        result = model.fit(disp="off", show_warning=False)

        # Conditional volatility from fitted model (divided back by 100)
        cond_vol = result.conditional_volatility / 100

        return cond_vol

    except Exception:
        return pd.Series(dtype=float)
