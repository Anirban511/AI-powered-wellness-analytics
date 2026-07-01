"""
Central configuration.

Everything tunable lives here so the app behaves the same locally (SQLite) and
in Docker (Postgres), and so the *business assumptions* used by the analytics
layer are explicit and auditable rather than buried in code.
"""
import os


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- Core ---
    APP_NAME = "Aura — Wellness Analytics"
    # SQLite by default (zero-setup local run). Docker compose overrides with Postgres.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aura.db")
    SEED_ON_START = _bool("SEED_ON_START", "true")

    # --- NLP ---
    # "vader"  -> fast lexicon model, no downloads, deterministic (default)
    # "transformer" -> HuggingFace distilbert SST-2 (heavier, needs internet on first run)
    SENTIMENT_BACKEND = os.getenv("SENTIMENT_BACKEND", "vader")
    TRANSFORMER_MODEL = os.getenv(
        "TRANSFORMER_MODEL", "distilbert-base-uncased-finetuned-sst-2-english"
    )

    # --- Demo data ---
    SEED_USERS = int(os.getenv("SEED_USERS", "45"))
    SEED_WEEKS = int(os.getenv("SEED_WEEKS", "8"))
    SEED_SEED = int(os.getenv("SEED_SEED", "7"))  # RNG seed for reproducible demos

    # --- Business / ROI model (ILLUSTRATIVE assumptions, all overridable) ---
    # Framing: a B2B corporate-wellness / EAP product sold per employee per month.
    PRICE_PER_SEAT_MONTH = float(os.getenv("PRICE_PER_SEAT_MONTH", "6.0"))   # USD
    # Value-delivered proxy: engaged users with reduced stress -> fewer lost days.
    AVG_LOADED_COST_PER_DAY = float(os.getenv("AVG_LOADED_COST_PER_DAY", "280.0"))  # USD/employee/day
    ABSENCE_DAYS_SAVED_PER_IMPROVED_USER = float(
        os.getenv("ABSENCE_DAYS_SAVED_PER_IMPROVED_USER", "1.8")
    )  # annual, illustrative
    # Engagement is the leading indicator of B2B renewal; used in the LTV note.
    ANNUAL_LOGO_CHURN_BASELINE = float(os.getenv("ANNUAL_LOGO_CHURN_BASELINE", "0.18"))


settings = Settings()
