"""Pydantic schemas — the API contract (request validation + typed responses)."""
import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field


class EntryIn(BaseModel):
    user_id: int
    text: str = Field(min_length=1, max_length=5000)


class SentimentOut(BaseModel):
    compound: float
    label: str
    pos: float
    neu: float
    neg: float
    keywords: list[str]


class RecommendationOut(BaseModel):
    id: Optional[int] = None
    category: str
    title: str
    body: str
    rationale: str
    accepted: bool = False

    class Config:
        from_attributes = True


class EntryOut(BaseModel):
    id: int
    user_id: int
    created_at: dt.datetime
    text: str
    sentiment: SentimentOut
    stress_score: float
    safety_flag: bool
    recommendations: list[RecommendationOut] = []


class TrendOut(BaseModel):
    user_id: int
    series: list[dict[str, Any]]      # [{date, stress, sentiment, ewma}]
    state: str                         # low | moderate | elevated | high
    trend: str                         # rising | falling | stable
    slope_per_day: float
    volatility: float
    forecast_next_week: float
    anomalies: list[dict[str, Any]]
    summary: str
