
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..db import PriceRecord


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


def compute_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    log_returns = np.log(df["close"] / df["close"].shift(1))
    rolling_vol = log_returns.rolling(window=window).std()
    return rolling_vol


def classify_risk(
    current_vol: float,
    historical_vol: pd.Series,
    low_q: float = 0.5,
    high_q: float = 0.8,
) -> str:
    low_threshold = historical_vol.quantile(low_q)
    high_threshold = historical_vol.quantile(high_q)
    if current_vol <= low_threshold:
        return "LOW"
    elif current_vol <= high_threshold:
        return "MEDIUM"
    else:
        return "HIGH"


def get_snapshot(db: Session, symbol: str) -> dict:
    from .drift import compute_drift
    df = get_prices_df(db, symbol)
    if df.empty:
        return {}

    vol_series = compute_volatility(df).dropna()
    if vol_series.empty:
        return {}

    current_vol = float(vol_series.iloc[-1])
    risk_level = classify_risk(current_vol, vol_series)
    drift_flag, drift_score = compute_drift(vol_series)

    return {
        "symbol": symbol,
        "currentRisk": risk_level,
        "currentVolatility": round(current_vol, 6),
        "driftFlag": drift_flag,
        "driftScore": round(drift_score, 4),
    }


def get_history(db: Session, symbol: str) -> dict:
    df = get_prices_df(db, symbol)
    if df.empty:
        return {"symbol": symbol, "points": []}

    vol_series = compute_volatility(df).dropna()
    historical_vol = vol_series

    points = []
    for dt, vol in vol_series.items():
        risk = classify_risk(float(vol), historical_vol)
        points.append({
            "date": dt.strftime("%Y-%m-%d"),
            "volatility": round(float(vol), 6),
            "riskLevel": risk,
        })

    return {"symbol": symbol, "points": points}
