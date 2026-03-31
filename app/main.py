from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yfinance as yf
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from .db import SessionLocal, Symbol, PriceRecord, User, WatchlistItem, init_db
from .models import DriftSummaryItem, RiskOverview, SymbolHistory, SymbolSnapshot
from .services.alerts import (
    get_alerts,
    get_alerts_for_user,
    mark_alert_read_for_user,
    mark_all_read_for_user,
)
from .services.analytics import get_history, get_snapshot, get_prices_df
from .services.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)
from .services.correlation import compute_correlation_matrix
from .services.data_quality import compute_data_quality
from .services.ingestion import fetch_and_store_prices, seed_symbols
from .services.predict import generate_forecast
from .services.snapshot_jobs import refresh_all_snapshots
from .services.var import compute_var

PROFILE_STORE_PATH = Path(__file__).resolve().parent / "user_profiles.json"


class SymbolCard(BaseModel):
    symbol: str
    name: str
    price: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0
    exchange: str = ""
    sector: str = ""


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1)


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class PreferencesUpdateRequest(BaseModel):
    emailAlerts: bool | None = None
    driftAlerts: bool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        if db.query(Symbol).count() == 0:
            seed_symbols(db)
        if db.query(PriceRecord).count() == 0:
            fetch_and_store_prices(db)
        _refresh_symbol_market_data(db)
        refresh_all_snapshots(db)
    finally:
        db.close()
    yield


app = FastAPI(title="QuantaRisk API", version="1.1.0", lifespan=lifespan)

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


def _get_profile_store() -> dict[str, Any]:
    if not PROFILE_STORE_PATH.exists():
        return {}
    try:
        return json.loads(PROFILE_STORE_PATH.read_text())
    except Exception:
        return {}


def _save_profile_store(store: dict[str, Any]) -> None:
    PROFILE_STORE_PATH.write_text(json.dumps(store, indent=2, sort_keys=True))


def _default_name(email: str) -> str:
    local = email.split("@")[0].replace(".", " ").replace("_", " ").strip()
    return local.title() or "User"


def _user_payload(user: User) -> dict[str, Any]:
    store = _get_profile_store()
    key = str(user.id)
    profile = store.get(key, {})
    prefs = profile.get("preferences", {})
    return {
        "id": user.id,
        "email": user.email,
        "name": profile.get("name") or _default_name(user.email),
        "preferences": {
            "emailAlerts": bool(prefs.get("emailAlerts", True)),
            "driftAlerts": bool(prefs.get("driftAlerts", True)),
        },
        "createdAt": user.created_at.isoformat() + "Z" if user.created_at else None,
    }


def _upsert_profile(user: User, *, name: str | None = None, preferences: dict[str, Any] | None = None) -> dict[str, Any]:
    store = _get_profile_store()
    key = str(user.id)
    current = store.get(key, {})
    if name is not None:
        current["name"] = name.strip()
    if preferences is not None:
        current["preferences"] = {
            "emailAlerts": bool(preferences.get("emailAlerts", current.get("preferences", {}).get("emailAlerts", True))),
            "driftAlerts": bool(preferences.get("driftAlerts", current.get("preferences", {}).get("driftAlerts", True))),
        }
    store[key] = current
    _save_profile_store(store)
    return _user_payload(user)


def _latest_price_fields(db: Session, symbol: str) -> dict[str, float]:
    rows = (
        db.query(PriceRecord)
        .filter(PriceRecord.symbol == symbol)
        .order_by(PriceRecord.date.desc())
        .limit(2)
        .all()
    )
    if not rows:
        return {"price": 0.0, "change": 0.0, "change_pct": 0.0}
    latest = float(rows[0].close or 0.0)
    previous = float(rows[1].close or latest) if len(rows) > 1 else latest
    change = latest - previous
    change_pct = (change / previous * 100.0) if previous else 0.0
    return {"price": latest, "change": change, "change_pct": change_pct}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not np.isfinite(number):
        return None
    return number


def _refresh_symbol_market_data(db: Session) -> None:
    symbols = db.query(Symbol).all()
    for item in symbols:
        changed = False
        latest = _latest_price_fields(db, item.symbol)
        if latest["price"]:
            item.price = latest["price"]
            item.change = latest["change"]
            item.change_pct = latest["change_pct"]
            changed = True

        needs_meta = not item.sector or not item.exchange
        if needs_meta:
            try:
                ticker = yf.Ticker(item.symbol)
                info = ticker.info or {}
            except Exception:
                info = {}
            sector = info.get("sector") or info.get("industry")
            exchange = info.get("exchange") or info.get("fullExchangeName")
            market_cap = info.get("marketCap")
            current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            previous_close = _safe_float(info.get("previousClose") or info.get("regularMarketPreviousClose"))
            if sector and not item.sector:
                item.sector = str(sector)
                changed = True
            if exchange and not item.exchange:
                item.exchange = str(exchange)
                changed = True
            if market_cap is not None:
                item.market_cap = str(market_cap)
                changed = True
            if current_price is not None:
                item.price = current_price
                changed = True
                if previous_close and previous_close != 0:
                    item.change = current_price - previous_close
                    item.change_pct = ((current_price - previous_close) / previous_close) * 100.0
                    changed = True
        if changed:
            db.add(item)
    db.commit()


def _symbol_card(db: Session, symbol_row: Symbol) -> SymbolCard:
    price = symbol_row.price
    change = symbol_row.change
    change_pct = symbol_row.change_pct
    if price is None:
        latest = _latest_price_fields(db, symbol_row.symbol)
        price = latest["price"]
        change = latest["change"]
        change_pct = latest["change_pct"]

    return SymbolCard(
        symbol=symbol_row.symbol,
        name=symbol_row.name or symbol_row.symbol,
        price=round(float(price or 0.0), 4),
        change=round(float(change or 0.0), 4),
        changePercent=round(float(change_pct or 0.0), 4),
        exchange=symbol_row.exchange or "",
        sector=symbol_row.sector or "",
    )


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
    return pd.DataFrame(
        [
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in records
        ]
    )


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "symbols": db.query(Symbol).count(),
        "prices": db.query(PriceRecord).count(),
    }


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _upsert_profile(user, name=_default_name(user.email))
    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=_user_payload(user))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email.lower(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=_user_payload(user))


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_payload(current_user)


@app.put("/api/me")
def update_me(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.email:
        email = payload.email.lower()
        duplicate = db.query(User).filter(User.email == email, User.id != current_user.id).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Email is already in use")
        current_user.email = email
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    updated = _upsert_profile(current_user, name=payload.name if payload.name is not None else None)
    return updated


@app.put("/api/me/preferences")
def update_preferences(
    payload: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    return _upsert_profile(
        current_user,
        preferences={
            "emailAlerts": payload.emailAlerts,
            "driftAlerts": payload.driftAlerts,
        },
    )


@app.get("/api/symbols", response_model=list[SymbolCard])
def get_symbols(db: Session = Depends(get_db)):
    _refresh_symbol_market_data(db)
    symbols = db.query(Symbol).order_by(Symbol.symbol.asc()).all()
    return [_symbol_card(db, s) for s in symbols]


@app.get("/api/symbols/search")
def search_symbols(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    q_lower = q.lower()
    matches = [
        s
        for s in db.query(Symbol).order_by(Symbol.symbol.asc()).all()
        if q_lower in s.symbol.lower() or q_lower in (s.name or "").lower()
    ]
    return [_symbol_card(db, s) for s in matches]


@app.get("/api/watchlist")
def get_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(WatchlistItem).filter(WatchlistItem.user_id == current_user.id).all()
    return [row.symbol for row in rows]


@app.post("/api/watchlist")
def add_watchlist_item(
    payload: WatchlistRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    symbol = payload.symbol.upper().strip()
    exists_symbol = db.query(Symbol).filter(Symbol.symbol == symbol).first()
    if not exists_symbol:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id, WatchlistItem.symbol == symbol)
        .first()
    )
    if not existing:
        db.add(WatchlistItem(user_id=current_user.id, symbol=symbol))
        db.commit()
    return {"ok": True, "symbol": symbol}


@app.delete("/api/watchlist/{symbol}")
def delete_watchlist_item(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id, WatchlistItem.symbol == symbol.upper())
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True, "symbol": symbol.upper()}


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
    sector_data: dict[str, dict[str, Any]] = {}
    for s in symbols:
        sector = s.sector or "Other"
        snap = get_snapshot(db, s.symbol)
        if sector not in sector_data:
            sector_data[sector] = {"sector": sector, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        sector_data[sector]["total"] += 1
        if snap:
            sector_data[sector][snap["currentRisk"]] += 1
    result = []
    for sd in sector_data.values():
        result.append(
            {
                "sector": sd["sector"],
                "symbolCount": sd["total"],
                "highRiskCount": sd["HIGH"],
                "mediumRiskCount": sd["MEDIUM"],
                "lowRiskCount": sd["LOW"],
                "dominantRisk": (
                    "HIGH"
                    if sd["HIGH"] >= sd["MEDIUM"] and sd["HIGH"] >= sd["LOW"]
                    else "MEDIUM" if sd["MEDIUM"] >= sd["LOW"] else "LOW"
                ),
            }
        )
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
            result.append(
                DriftSummaryItem(
                    symbol=s.symbol,
                    driftFlag=snap["driftFlag"],
                    driftScore=snap["driftScore"],
                )
            )
    return result


@app.get("/api/data-quality")
def get_data_quality(db: Session = Depends(get_db)):
    symbols = db.query(Symbol).all()
    return [compute_data_quality(db, s.symbol) for s in symbols]


@app.get("/api/alerts")
def get_alerts_route(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    if limit > 0 and not get_alerts(db, limit=1):
        refresh_all_snapshots(db)
    return get_alerts(db, limit=limit)


@app.get("/api/my-alerts")
def get_my_alerts(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if limit > 0 and not get_alerts(db, limit=1):
        refresh_all_snapshots(db)
    return get_alerts_for_user(db, current_user.id, limit=limit)


@app.post("/api/alerts/{alert_id}/read")
def mark_alert_read_endpoint(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = mark_alert_read_for_user(db, current_user.id, alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "alertId": alert_id}


@app.post("/api/alerts/read-all")
def mark_alerts_read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = mark_all_read_for_user(db, current_user.id)
    return {"ok": True, "updated": count}


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
    cumulative = close / float(close.iloc[0])
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max

    fundamentals: dict[str, Any] = {}
    try:
        fundamentals = yf.Ticker(symbol).info or {}
    except Exception:
        fundamentals = {}

    return {
        "symbol": symbol,
        "pe": _safe_float(fundamentals.get("trailingPE") or fundamentals.get("forwardPE")) or 0.0,
        "eps": _safe_float(fundamentals.get("trailingEps") or fundamentals.get("forwardEps")) or 0.0,
        "pb": _safe_float(fundamentals.get("priceToBook")) or 0.0,
        "ps": _safe_float(fundamentals.get("priceToSalesTrailing12Months")) or 0.0,
        "debtToEquity": _safe_float(fundamentals.get("debtToEquity")) or 0.0,
        "currentRatio": _safe_float(fundamentals.get("currentRatio")) or 0.0,
        "roe": _safe_float(fundamentals.get("returnOnEquity")) or 0.0,
        "roa": _safe_float(fundamentals.get("returnOnAssets")) or 0.0,
        "grossMargin": _safe_float(fundamentals.get("grossMargins")) or 0.0,
        "operatingMargin": _safe_float(fundamentals.get("operatingMargins")) or 0.0,
        "netMargin": _safe_float(fundamentals.get("profitMargins")) or 0.0,
        "dividendYield": _safe_float(fundamentals.get("dividendYield")) or 0.0,
        "beta": _safe_float(fundamentals.get("beta")) or 0.0,
        "sharpeRatio": sharpe,
        "maxDrawdown": round(float(drawdown.min()), 6),
        "annualizedReturn": round(ann_return, 6),
        "annualizedVolatility": round(ann_vol, 6),
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
