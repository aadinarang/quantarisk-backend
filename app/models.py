from typing import List, Literal

from pydantic import BaseModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class SymbolInfo(BaseModel):
    symbol: str
    name: str


class RiskOverview(BaseModel):
    totalSymbols: int
    highRiskCount: int
    mediumRiskCount: int
    lowRiskCount: int
    lastUpdated: str  # ISO datetime string


class SymbolSnapshot(BaseModel):
    symbol: str
    currentRisk: RiskLevel
    currentVolatility: float
    driftFlag: bool
    driftScore: float
    volSource: str = "rolling"  # default fallback


class HistoryPoint(BaseModel):
    date: str  # ISO date string
    volatility: float
    riskLevel: RiskLevel


class SymbolHistory(BaseModel):
    symbol: str
    points: List[HistoryPoint]


class DriftSummaryItem(BaseModel):
    symbol: str
    driftFlag: bool
    driftScore: float
