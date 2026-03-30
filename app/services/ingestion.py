from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from ..db import PriceRecord, SessionLocal, Symbol, init_db

WATCHLIST = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp",
    "TSLA": "Tesla Inc.",
    "SPY":  "SPDR S&P 500 ETF",
    "NVDA": "NVIDIA Corp",
    "AMZN": "Amazon.com Inc.",
}


def seed_symbols(db: Session):
    for symbol, name in WATCHLIST.items():
        exists = db.query(Symbol).filter_by(symbol=symbol).first()
        if not exists:
            db.add(Symbol(symbol=symbol, name=name))
    db.commit()


def fetch_and_store_prices(db: Session, period_days: int = 365):
    start = date.today() - timedelta(days=period_days)
    for symbol in WATCHLIST:
        df = yf.download(symbol, start=start.isoformat(), auto_adjust=True, progress=False)
        if df.empty:
            print(f"No data returned for {symbol}")
            continue

        # Flatten MultiIndex columns if present (yfinance quirk)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Reset index to get Date as a column
        df.reset_index(inplace=True)

        # Rename to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Force date column to plain Python date
        df["date"] = pd.to_datetime(df["date"]).dt.date

        for _, row in df.iterrows():
            record_date = row["date"]  # already a plain date object now

            exists = db.query(PriceRecord).filter_by(
                symbol=symbol, date=record_date
            ).first()
            if not exists:
                db.add(PriceRecord(
                    symbol=symbol,
                    date=record_date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ))
        db.commit()
        print(f"Stored prices for {symbol}")

def run_ingestion():
    init_db()
    db = SessionLocal()
    try:
        seed_symbols(db)
        fetch_and_store_prices(db)
    finally:
        db.close()


if __name__ == "__main__":
    run_ingestion()
