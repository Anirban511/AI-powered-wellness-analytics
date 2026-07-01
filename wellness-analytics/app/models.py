"""
ORM models — the data model behind the whole pipeline.

Design notes (the kind an interviewer probes):
- JournalEntry stores BOTH the raw text and the derived NLP/ML signals so we never
  recompute on read and analytics queries stay cheap.
- EngagementEvent is a thin event log. It powers the engagement funnel and retention
  cohorts without coupling analytics to the feature tables.
- Recommendation.accepted closes the funnel loop (was the advice acted on?).
"""
import datetime as dt

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Index
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    # cohort_week = ISO date of the Monday of the signup week (retention cohorts).
    cohort_week = Column(String(10), index=True)
    # persona is demo-only metadata describing the synthetic trajectory.
    persona = Column(String(32), default="real")

    entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    events = relationship("EngagementEvent", back_populates="user", cascade="all, delete-orphan")


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    text = Column(Text, nullable=False)

    # --- NLP outputs ---
    sentiment_compound = Column(Float)   # VADER/normalised score in [-1, 1]
    sentiment_label = Column(String(16))  # positive | neutral | negative
    pos = Column(Float)
    neu = Column(Float)
    neg = Column(Float)
    keywords = Column(JSON)               # extracted topic/stressor keywords

    # --- ML / derived ---
    stress_score = Column(Float)          # 0..100 composite
    safety_flag = Column(Boolean, default=False)

    user = relationship("User", back_populates="entries")


Index("ix_entries_user_created", JournalEntry.user_id, JournalEntry.created_at)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    category = Column(String(32))
    title = Column(String(160))
    body = Column(Text)
    rationale = Column(Text)              # why this was surfaced (explainability)
    accepted = Column(Boolean, default=False)  # funnel: was it acted on?

    user = relationship("User", back_populates="recommendations")


class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    event_type = Column(String(40))      # journaled | viewed_dashboard | viewed_report | accepted_reco
    meta = Column(JSON)

    user = relationship("User", back_populates="events")


Index("ix_events_user_type_created", EngagementEvent.user_id, EngagementEvent.event_type, EngagementEvent.created_at)
