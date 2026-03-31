from typing import List, Literal
from pydantic import BaseModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]

class SymbolInfo(BaseModel):
    symbol: str
    name: str
    price: float = 0.0
    change: float = 0.0
    changePercent: float = 0.0
    sector: str = ""
    exchange: str = ""

class RiskOverview(BaseModel):
    totalSymbols: int
    highRiskCount: int
    mediumRiskCount: int
    lowRiskCount: int
    lastUpdated: str

class SymbolSnapshot(BaseModel):
    symbol: str
    currentRisk: RiskLevel
    currentVolatility: float
    driftFlag: bool
    driftScore: float
    volSource: str = "rolling"

class HistoryPoint(BaseModel):
    date: str
    volatility: float
    riskLevel: RiskLevel

class SymbolHistory(BaseModel):
    symbol: str
    points: List[HistoryPoint]

class DriftSummaryItem(BaseModel):
    symbol: str
    driftFlag: bool
    driftScore: float
