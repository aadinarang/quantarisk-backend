import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from ..db import PriceRecord
from .garch import fit_garch_forecast, get_garch_volatility_series


def get_prices_df(db: Session, symbol: str) -> pd.DataFrame:
    records = (
        db.query(PriceRecord)
        .filter_by(symbol=symbol)
        .order_by(PriceRecord.date)
        .all()
    )
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([{
        "date": r.date,
        "close": r.close
    } for r in records])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def compute_log_returns(df: pd.DataFrame) -> pd.Series:
    """Compute daily log returns from closing prices."""
    return np.log(df["close"] / df["close"].shift(1))


def compute_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Compute rolling volatility (20-day rolling std of log returns).
    Used as fallback when GARCH is unavailable.
    """
    log_returns = compute_log_returns(df)
    return log_returns.rolling(window=window).std()


def classify_risk(
    current_vol: float,
    historical_vol: pd.Series,
    low_q: float = 0.5,
    high_q: float = 0.8,
) -> str:
    """
    Classify risk level based on where current volatility
    sits in the historical distribution.
    """
    low_threshold = historical_vol.quantile(low_q)
    high_threshold = historical_vol.quantile(high_q)

    if current_vol <= low_threshold:
        return "LOW"
    elif current_vol <= high_threshold:
        return "MEDIUM"
    else:
        return "HIGH"


def get_snapshot(db: Session, symbol: str) -> dict:
    """
    Build a full risk snapshot for a symbol.
    
    Uses GARCH(1,1) to forecast next-day volatility.
    Falls back to 20-day rolling std if GARCH fails or
    insufficient data is available.
    """
    from .drift import compute_drift

    df = get_prices_df(db, symbol)
    if df.empty:
        return {}

    log_returns = compute_log_returns(df).dropna()
    if log_returns.empty:
        return {}

    # --- Primary: GARCH forecast ---
    garch_vol = fit_garch_forecast(log_returns)

    # --- Fallback: rolling std ---
    rolling_vol_series = compute_volatility(df).dropna()
    if rolling_vol_series.empty:
        return {}

    rolling_vol = float(rolling_vol_series.iloc[-1])

    # Decide which volatility estimate to use
    if garch_vol is not None:
        current_vol = garch_vol
        vol_source = "garch"
    else:
        current_vol = rolling_vol
        vol_source = "rolling"

    # Use GARCH conditional vol series if available for baseline,
    # otherwise use rolling series
    garch_series = get_garch_volatility_series(log_returns)
    baseline_series = garch_series if not garch_series.empty else rolling_vol_series

    # Classify risk using the baseline distribution
    risk_level = classify_risk(current_vol, baseline_series)

    # Drift detection on the baseline series
    drift_flag, drift_score = compute_drift(baseline_series)

    return {
        "symbol": symbol,
        "currentRisk": risk_level,
        "currentVolatility": round(current_vol, 6),
        "driftFlag": drift_flag,
        "driftScore": round(drift_score, 4),
        "volSource": vol_source,  # tells you if GARCH or rolling was used
    }


def get_history(db: Session, symbol: str) -> dict:
    """
    Build volatility history for chart display.
    
    Uses GARCH conditional volatility series if available,
    falls back to rolling std series.
    """
    df = get_prices_df(db, symbol)
    if df.empty:
        return {"symbol": symbol, "points": []}

    log_returns = compute_log_returns(df).dropna()

    # Try GARCH series first
    garch_series = get_garch_volatility_series(log_returns)

    if not garch_series.empty:
        vol_series = garch_series
    else:
        vol_series = compute_volatility(df).dropna()

    if vol_series.empty:
        return {"symbol": symbol, "points": []}

    points = []
    for dt, vol in vol_series.items():
        risk = classify_risk(float(vol), vol_series)
        points.append({
            "date": dt.strftime("%Y-%m-%d"),
            "volatility": round(float(vol), 6),
            "riskLevel": risk,
        })

    return {"symbol": symbol, "points": points}
