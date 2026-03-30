import os

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantarisk.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Symbol(Base):
    __tablename__ = "symbols"
    symbol     = Column(String, primary_key=True)
    name       = Column(String)
    sector     = Column(String, nullable=True)
    exchange   = Column(String, nullable=True)
    market_cap = Column(String, nullable=True)
    price      = Column(Float,  nullable=True)
    change     = Column(Float,  nullable=True)
    change_pct = Column(Float,  nullable=True)


class PriceRecord(Base):
    __tablename__ = "prices"
    id     = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True)
    date   = Column(Date,   index=True)
    open   = Column(Float)
    high   = Column(Float)
    low    = Column(Float)
    close  = Column(Float)
    volume = Column(Float)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String, index=True)
    date        = Column(Date)
    volatility  = Column(Float)
    risk_level  = Column(String)
    drift_flag  = Column(Boolean)
    drift_score = Column(Float)
    vol_source  = Column(String, nullable=True)
    computed_at = Column(DateTime)


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    symbol           = Column(String, index=True)
    pe               = Column(Float, nullable=True)
    eps              = Column(Float, nullable=True)
    pb               = Column(Float, nullable=True)
    ps               = Column(Float, nullable=True)
    debt_to_equity   = Column(Float, nullable=True)
    current_ratio    = Column(Float, nullable=True)
    roe              = Column(Float, nullable=True)
    roa              = Column(Float, nullable=True)
    gross_margin     = Column(Float, nullable=True)
    operating_margin = Column(Float, nullable=True)
    net_margin       = Column(Float, nullable=True)
    dividend_yield   = Column(Float, nullable=True)
    beta             = Column(Float, nullable=True)
    sharpe_ratio     = Column(Float, nullable=True)
    max_drawdown     = Column(Float, nullable=True)


class DataQualityRecord(Base):
    __tablename__ = "data_quality"
    id                     = Column(Integer, primary_key=True, autoincrement=True)
    symbol                 = Column(String, index=True)
    total_records          = Column(Integer)
    missing_values         = Column(Integer)
    date_gaps              = Column(Integer)
    price_range_violations = Column(Integer)
    status                 = Column(String)
    completeness           = Column(Float)
    computed_at            = Column(DateTime, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id        = Column(String, primary_key=True)
    timestamp = Column(DateTime, index=True)
    symbol    = Column(String, index=True)
    type      = Column(String)
    severity  = Column(String)
    message   = Column(String)
    detail    = Column(Text)
    read      = Column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime)


class UserAlertState(Base):
    __tablename__ = "user_alert_states"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    user_id  = Column(Integer, ForeignKey("users.id"))
    alert_id = Column(String,  ForeignKey("alerts.id"))
    read     = Column(Boolean, default=False)
    read_at  = Column(DateTime, nullable=True)


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol  = Column(String)


def init_db():
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(engine)
    if inspector.has_table("symbols"):
        cols = [c["name"] for c in inspector.get_columns("symbols")]
        if "sector" not in cols:
            Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
