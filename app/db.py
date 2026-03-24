import os
from sqlalchemy import (
    create_engine, Column, String, Float,
    Boolean, DateTime, Date, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantarisk.db")

# SQLite needs check_same_thread=False; Postgres doesn't need it
# connect_args is ignored by Postgres so this is safe for both
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# --- DB Table Models ---

class Symbol(Base):
    __tablename__ = "symbols"
    symbol = Column(String, primary_key=True)
    name = Column(String)


class PriceRecord(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, index=True)
    date = Column(Date)
    volatility = Column(Float)
    risk_level = Column(String)
    drift_flag = Column(Boolean)
    drift_score = Column(Float)
    computed_at = Column(DateTime)


def init_db():
    Base.metadata.create_all(bind=engine)
