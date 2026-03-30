from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import SessionLocal, Symbol, init_db
from .models import (
    DriftSummaryItem,
    RiskOverview,
    SymbolHistory,
    SymbolInfo,
    SymbolSnapshot,
)
from .services.analytics import get_history, get_snapshot


# --- Lifespan (runs on startup/shutdown) ---
@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


# --- App created ONCE with lifespan ---
app = FastAPI(title="QuantaRisk API", version="1.0.0", lifespan=lifespan)

# --- Middleware added to the ONE app ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- DB dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Routes ---
@app.get("/api/symbols", response_model=list[SymbolInfo])
def get_symbols(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    return [SymbolInfo(symbol=s.symbol, name=s.name) for s in symbols]


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
def get_risk_snapshot(
    symbol: str = Query(...), db: Session = Depends(get_db)
):
    snap = get_snapshot(db, symbol)
    if not snap:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")
    return SymbolSnapshot(**snap)


@app.get("/api/risk/history", response_model=SymbolHistory)
def get_risk_history(
    symbol: str = Query(...), db: Session = Depends(get_db)
):
    history = get_history(db, symbol)
    return SymbolHistory(**history)


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

@app.get("/api/health")
def health():
    return {"status": "ok"}