"""
Snapshot materialization and alert generation.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..db import RiskSnapshot, Symbol
from .alerts import generate_alerts
from .analytics import get_snapshot


def refresh_all_snapshots(db: Session) -> None:
    symbols = db.query(Symbol).all()

    for sym in symbols:
        previous_row = (
            db.query(RiskSnapshot)
            .filter_by(symbol=sym.symbol)
            .order_by(RiskSnapshot.computed_at.desc())
            .first()
        )

        previous_snapshot = None
        if previous_row:
            previous_snapshot = {
                "symbol": previous_row.symbol,
                "currentRisk": previous_row.risk_level,
                "currentVolatility": previous_row.volatility,
                "driftFlag": previous_row.drift_flag,
                "driftScore": previous_row.drift_score,
                "volSource": previous_row.vol_source,
            }

        current_snapshot = get_snapshot(db, sym.symbol)
        if not current_snapshot:
            continue

        row = RiskSnapshot(
            symbol=sym.symbol,
            date=datetime.utcnow().date(),
            volatility=current_snapshot["currentVolatility"],
            risk_level=current_snapshot["currentRisk"],
            drift_flag=current_snapshot["driftFlag"],
            drift_score=current_snapshot["driftScore"],
            vol_source=current_snapshot["volSource"],
            computed_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()

        generate_alerts(
            db=db,
            symbol=sym.symbol,
            snapshot=current_snapshot,
            previous_snapshot=previous_snapshot,
        )