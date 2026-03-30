from contextlib import asynccontextmanager
from datetime import datetime
from typing import List
import numpy as np

from fastapi import Depends, FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import SessionLocal, Symbol, PriceRecord, init_db
from .models import (
    DriftSummaryItem,
    RiskOverview,
    SymbolHistory,
    SymbolInfo,
    SymbolSnapshot,
)
from .services.analytics import get_history, get_snapshot, get_prices_df
from .services.alerts import get_alerts
from .services.correlation import compute_correlation_matrix
from .services.data_quality import compute_data_quality
from .services.var import compute_var
from .services.predict import generate_forecast

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="QuantaRisk API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "META": "Technology", "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary", "JPM": "Financials", "BAC": "Financials",
    "GS": "Financials", "JNJ": "Healthcare", "PFE": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "SPY": "ETF", "QQQ": "ETF",
}

def _get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), "Other")

def _get_full_prices_df(db: Session, symbol: str):
    import pandas as pd
    records = (
        db.query(PriceRecord)
        .filter_by(symbol=symbol)
        .order_by(PriceRecord.date)
        .all()
    )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([{
        "date": r.date, "open": r.open, "high": r.high,
        "low": r.low, "close": r.close, "volume": r.volume,
    } for r in records])

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/symbols", response_model=list[SymbolInfo])
def get_symbols(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    return [SymbolInfo(symbol=s.symbol, name=s.name) for s in symbols]

@app.get("/api/symbols/search")
def search_symbols(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    q_lower = q.lower()
    symbols = db.query(Symbol).all()
    return [
        {"symbol": s.symbol, "name": s.name}
        for s in symbols
        if q_lower in s.symbol.lower() or q_lower in (s.name or "").lower()
    ]

@app.get("/api/risk/overview", response_model=RiskOverview)
def get_risk_overview(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for s in symbols:
        snap = get_snapshot(db, s.symbol)
        if snap:
            counts[snap["currentRisk"]] += 1
    return RiskOverview(
        totalSymbols=len(symbols),
        highRiskCount=counts["HIGH"],
        mediumRiskCount=counts["MEDIUM"],
        lowRiskCount=counts["LOW"],
        lastUpdated=datetime.utcnow().isoformat() + "Z",
    )

@app.get("/api/risk/snapshot", response_model=SymbolSnapshot)
def get_risk_snapshot(symbol: str = Query(...), db: Session = Depends(get_db)):
    snap = get_snapshot(db, symbol)
    if not snap:
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")
    return SymbolSnapshot(**snap)

@app.get("/api/risk/history", response_model=SymbolHistory)
def get_risk_history(symbol: str = Query(...), db: Session = Depends(get_db)):
    history = get_history(db, symbol)
    return SymbolHistory(**history)

@app.get("/api/risk/sectors")
def get_risk_sectors(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    sector_data: dict = {}
    for s in symbols:
        sector = _get_sector(s.symbol)
        snap = get_snapshot(db, s.symbol)
        if sector not in sector_data:
            sector_data[sector] = {"sector": sector, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        sector_data[sector]["total"] += 1
        if snap:
            sector_data[sector][snap["currentRisk"]] += 1
    result = []
    for sd in sector_data.values():
        result.append({
            "sector": sd["sector"],
            "symbolCount": sd["total"],
            "highRiskCount": sd["HIGH"],
            "mediumRiskCount": sd["MEDIUM"],
            "lowRiskCount": sd["LOW"],
            "dominantRisk": (
                "HIGH" if sd["HIGH"] >= sd["MEDIUM"] and sd["HIGH"] >= sd["LOW"]
                else "MEDIUM" if sd["MEDIUM"] >= sd["LOW"] else "LOW"
            ),
        })
    return result

@app.get("/api/risk/correlation")
def get_correlation(db: Session = Depends(get_db)):
    symbols = [s.symbol for s in db.query(Symbol).all()]
    return compute_correlation_matrix(db, symbols)

@app.get("/api/risk/var")
def get_var(symbol: str = Query(...), db: Session = Depends(get_db)):
    df = get_prices_df(db, symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for symbol: {symbol}")
    result = compute_var(df["close"])
    return {"symbol": symbol, **result}

@app.get("/api/drift/summary", response_model=list[DriftSummaryItem])
def get_drift_summary(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    result = []
    for s in symbols:
        snap = get_snapshot(db, s.symbol)
        if snap:
            result.append(DriftSummaryItem(
                symbol=s.symbol,
                driftFlag=snap["driftFlag"],
                driftScore=snap["driftScore"],
            ))
    return result

@app.get("/api/data-quality")
def get_data_quality(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    return [compute_data_quality(db, s.symbol) for s in symbols]

@app.get("/api/alerts")
def get_alerts_route(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return get_alerts(db, limit=limit)

@app.get("/api/ratios")
def get_ratios(symbol: str = Query(...), db: Session = Depends(get_db)):
    df = get_prices_df(db, symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for symbol: {symbol}")
    close = df["close"].dropna()
    if len(close) < 2:
        raise HTTPException(status_code=404, detail="Insufficient price data")
    log_returns = np.log(close / close.shift(1)).dropna()
    ann_return = float(log_returns.mean() * 252)
    ann_vol = float(log_returns.std() * np.sqrt(252))
    sharpe = round(ann_return / ann_vol, 4) if ann_vol > 0 else 0.0
    cumulative = (1 + log_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return {
        "symbol": symbol,
        "annualizedReturn": round(ann_return, 6),
        "annualizedVolatility": round(ann_vol, 6),
        "sharpeRatio": sharpe,
        "maxDrawdown": round(float(drawdown.min()), 6),
        "dataPoints": len(close),
    }

@app.get("/api/predict")
def get_predict(
    symbol: str = Query(...),
    days: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    df = _get_full_prices_df(db, symbol)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data for symbol: {symbol}")
    return generate_forecast(symbol, df, horizon=days)
