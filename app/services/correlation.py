"""Pairwise Pearson correlation matrix across all tracked symbols."""
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..db import PriceRecord


def compute_correlation_matrix(db: Session, symbols: list[str]) -> dict:
    """
    Compute the NxN Pearson correlation matrix of daily log returns
    for all tracked symbols, aligned to a common date index.

    Returns:
        {
          "symbols": ["AAPL", "MSFT", ...],
          "matrix":  [[1.0, 0.78, ...], ...]   # NxN
        }
    """
    if not symbols:
        return {"symbols": [], "matrix": []}

    # Build a DataFrame of close prices indexed by date
    series = {}
    for sym in symbols:
        records = (
            db.query(PriceRecord)
            .filter_by(symbol=sym)
            .order_by(PriceRecord.date)
            .all()
        )
        if records:
            dates  = [r.date for r in records]
            closes = [r.close for r in records]
            series[sym] = pd.Series(closes, index=pd.to_datetime(dates))

    if not series:
        return {"symbols": [], "matrix": []}

    # Align to common date range, forward-fill gaps
    df = pd.DataFrame(series).ffill()

    # Compute log returns
    returns = np.log(df / df.shift(1)).dropna()

    if returns.empty or len(returns) < 5:
        n = len(symbols)
        identity = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        return {"symbols": symbols, "matrix": identity}

    # Keep only columns with enough data
    valid_cols = [c for c in returns.columns if returns[c].notna().sum() >= 5]
    returns = returns[valid_cols].dropna()

    corr_df = returns.corr(method="pearson")

    # Build the result using the requested symbol order
    result_syms = [s for s in symbols if s in corr_df.columns]
    corr_df = corr_df.reindex(index=result_syms, columns=result_syms)
    corr_df = corr_df.fillna(0.0)

    matrix = [[round(float(corr_df.loc[a, b]), 4) for b in result_syms] for a in result_syms]

    return {"symbols": result_syms, "matrix": matrix}
