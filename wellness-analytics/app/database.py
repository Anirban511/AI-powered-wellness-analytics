"""
Database wiring (SQLAlchemy).

Kept deliberately DB-agnostic: the same ORM models run on SQLite (local dev) and
Postgres (Docker) by switching DATABASE_URL only. No raw SQL in the app layer.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# check_same_thread is a SQLite-only flag; harmless to compute conditionally.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they do not exist (idempotent)."""
    from app import models  # noqa: F401  (register models on Base)
    Base.metadata.create_all(bind=engine)
