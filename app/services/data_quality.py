"""Per-symbol OHLCV ingestion validation and data quality reporting."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..db import PriceRecord, DataQualityRecord as DQRecord


# ── Validation helpers ────────────────────────────────────────────

def validate_ohlcv(df: pd.DataFrame) -> list[str]:
    """
    Run four quality checks on a raw OHLCV DataFrame.
    Returns a list of error strings (empty = all passed).
    """
    errors = []
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing column: {col}")

    if "close" in df.columns:
        if (df["close"] <= 0).any():
            errors.append("close prices must be positive")

    if "volume" in df.columns:
        if (df["volume"] < 0).any():
            errors.append("volume must be non-negative")

    if "date" in df.columns and df["date"].isnull().any():
        errors.append("date column has nulls")

    return errors


def count_null_values(df: pd.DataFrame) -> int:
    """Count NaN values in the close column."""
    if "close" not in df.columns:
        return 0
    return int(df["close"].isnull().sum())


def count_date_gaps(df: pd.DataFrame, max_gap_days: int = 3) -> int:
    """
    Count gaps between consecutive dates that exceed max_gap_days.
    Holidays and weekends (up to 3 calendar days) are expected.
    """
    if "date" not in df.columns or len(df) < 2:
        return 0
    dates = pd.to_datetime(df["date"]).sort_values()
    diffs = (dates.diff().dt.days).dropna()
    return int((diffs > max_gap_days).sum())


def count_price_range_violations(df: pd.DataFrame) -> int:
    """
    Count rows with obvious data errors:
    - high < low
    - close outside [low, high]
    - single-day return > ±50%
    """
    if not all(c in df.columns for c in ["open", "high", "low", "close"]):
        return 0
    violations = 0
    violations += int((df["high"] < df["low"]).sum())
    violations += int(((df["close"] < df["low"]) | (df["close"] > df["high"])).sum())
    if "close" in df.columns and len(df) > 1:
        log_ret = np.log(df["close"] / df["close"].shift(1)).dropna()
        violations += int((log_ret.abs() > 0.5).sum())
    return violations


# ── Per-symbol quality audit ──────────────────────────────────────

def compute_data_quality(db: Session, symbol: str, expected_trading_days: int = 252) -> dict:
    """
    Run all four validation checks against the stored price records
    for a given symbol and return a quality summary dict.
    """
    records = (
        db.query(PriceRecord)
        .filter_by(symbol=symbol)
        .order_by(PriceRecord.date)
        .all()
    )

    if not records:
        return {
            "symbol": symbol,
            "totalRecords": 0,
            "missingValues": 0,
            "dateGaps": 0,
            "priceRangeViolations": 0,
            "lastIngested": datetime.utcnow().isoformat() + "Z",
            "status": "FAIL",
            "completeness": 0.0,
        }

    df = pd.DataFrame([{
        "date":   r.date,
        "open":   r.open,
        "high":   r.high,
        "low":    r.low,
        "close":  r.close,
        "volume": r.volume,
    } for r in records])

    total          = len(df)
    missing        = count_null_values(df)
    gaps           = count_date_gaps(df)
    range_viol     = count_price_range_violations(df)
    last_ingested  = datetime.utcnow().isoformat() + "Z"
    completeness   = round(min(1.0, total / expected_trading_days), 4)

    # Determine status
    if range_viol > 0 or missing > total * 0.05:
        status = "FAIL"
    elif missing > 0 or gaps > 0:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "symbol":               symbol,
        "totalRecords":         total,
        "missingValues":        missing,
        "dateGaps":             gaps,
        "priceRangeViolations": range_viol,
        "lastIngested":         last_ingested,
        "status":               status,
        "completeness":         completeness,
    }
