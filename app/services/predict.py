"""
PyTorch LSTM-based forecast service for QuantaRisk.

Based on the provided Stock-Price-Predictor repo:
- input features: Open, High, Low, Close, Volume
- sequence length: 60
- output: next-step predicted Close
- recursive forecasting for multi-step horizons
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False
    torch = None

from .model_registry import model_registry


def _build_feature_frame(prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Expect a DataFrame with columns:
    open, high, low, close, volume
    """
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in prices_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for forecasting: {missing}")

    feat = prices_df[required].copy()
    feat = feat.dropna()
    return feat


def _fallback_bands(point_forecast: list[float], prices_df: pd.DataFrame) -> tuple[list[float], list[float]]:
    """
    Practical fallback uncertainty bands.

    Since the selected repo does not include MC-dropout or predictive intervals,
    we estimate a simple volatility-based band from historical close returns.
    """
    close = prices_df["close"].dropna()
    if len(close) < 20:
        upper = [round(p * 1.05, 4) for p in point_forecast]
        lower = [round(max(p * 0.95, 0.01), 4) for p in point_forecast]
        return upper, lower

    log_ret = np.log(close / close.shift(1)).dropna()
    daily_vol = float(log_ret.tail(20).std())
    daily_vol = max(daily_vol, 0.005)

    upper = []
    lower = []

    for i, p in enumerate(point_forecast, start=1):
        width = np.exp(daily_vol * np.sqrt(i))
        upper.append(round(float(p * width), 4))
        lower.append(round(float(max(p / width, 0.01)), 4))

    return upper, lower


def _recursive_lstm_forecast(prices_df: pd.DataFrame, horizon: int) -> dict | None:
    loaded = model_registry.get_default_model()
    if loaded is None or not TORCH_AVAILABLE:
        return None

    seq_len = loaded.sequence_length
    feat = _build_feature_frame(prices_df)

    if len(feat) < seq_len:
        return None

    scaler = MinMaxScaler()
    features_scaled = scaler.fit_transform(feat.values)

    last_seq = features_scaled[-seq_len:]
    current_seq = torch.tensor(last_seq, dtype=torch.float32).unsqueeze(0)

    predictions_scaled = []

    loaded.model.eval()
    with torch.no_grad():
        for _ in range(horizon):
            pred = loaded.model(current_seq).item()
            predictions_scaled.append(pred)

            # Carry forward the most recent feature row, update Close only.
            next_features = current_seq[0, -1, :].clone()
            next_features[3] = pred  # Close index
            next_seq = torch.cat(
                (current_seq[:, 1:, :], next_features.unsqueeze(0).unsqueeze(0)),
                dim=1,
            )
            current_seq = next_seq

    predicted_close = scaler.inverse_transform(
        [[0, 0, 0, pred, 0] for pred in predictions_scaled]
    )[:, 3]

    point_forecast = [round(float(x), 4) for x in predicted_close]
    upper, lower = _fallback_bands(point_forecast, prices_df)

    return {
        "forecastPrices": point_forecast,
        "upperBand": upper,
        "lowerBand": lower,
    }


def _math_forecast(prices_df: pd.DataFrame, horizon: int) -> dict:
    """
    Backup forecast if PyTorch model is unavailable.
    """
    close = prices_df["close"].dropna()
    if close.empty:
        raise ValueError("No close-price data available for fallback forecast")

    if len(close) < 20:
        last = float(close.iloc[-1])
        return {
            "forecastPrices": [round(last, 4)] * horizon,
            "upperBand": [round(last * 1.05, 4)] * horizon,
            "lowerBand": [round(last * 0.95, 4)] * horizon,
        }

    last_price = float(close.iloc[-1])
    ema5 = close.ewm(span=5).mean()
    trend = (
        (float(ema5.iloc[-1]) - float(ema5.iloc[-6])) / float(ema5.iloc[-6])
        if len(ema5) >= 6 else 0.0
    )
    trend = max(min(trend, 0.02), -0.02)

    ma60 = float(close.rolling(60, min_periods=20).mean().iloc[-1])
    rev_k = 0.02

    log_ret = np.log(close / close.shift(1)).dropna()
    daily_vol = float(log_ret.tail(20).std())
    daily_vol = max(daily_vol, 0.005)

    rng = np.random.default_rng(42)
    trajectories = []

    for _ in range(100):
        path = [last_price]
        for i in range(horizon):
            prev = path[-1]
            noise = rng.normal(0, daily_vol)
            reversion = rev_k * (ma60 / prev - 1) if prev > 0 else 0.0
            daily_ret = trend + reversion + noise
            nxt = max(prev * np.exp(daily_ret), 0.01)
            path.append(nxt)
        trajectories.append(path[1:])

    arr = np.array(trajectories)
    point = arr.mean(axis=0)
    upper = np.percentile(arr, 95, axis=0)
    lower = np.percentile(arr, 5, axis=0)

    return {
        "forecastPrices": [round(float(x), 4) for x in point],
        "upperBand": [round(float(x), 4) for x in upper],
        "lowerBand": [round(float(x), 4) for x in lower],
    }


def generate_forecast(symbol: str, prices_df: pd.DataFrame, horizon: int = 10) -> dict:
    """
    Generate a forecast for `symbol` over `horizon` future business days.

    prices_df must contain:
    - open
    - high
    - low
    - close
    - volume
    """
    horizon = max(1, min(horizon, 30))

    last_date = datetime.utcnow().date()
    forecast_dates = []
    d = last_date
    while len(forecast_dates) < horizon:
        d += timedelta(days=1)
        if d.weekday() < 5:
            forecast_dates.append(d.isoformat())

    result = _recursive_lstm_forecast(prices_df, horizon=horizon)
    version = "lstm-v1" if result is not None else "math-v1"

    if result is None:
        result = _math_forecast(prices_df, horizon=horizon)

    return {
        "symbol": symbol,
        "forecastDates": forecast_dates,
        "forecastPrices": result["forecastPrices"],
        "upperBand": result["upperBand"],
        "lowerBand": result["lowerBand"],
        "modelVersion": version,
    }