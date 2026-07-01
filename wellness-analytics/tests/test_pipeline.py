"""
Aura — sanity test suite.

These tests pin the *behavioural contracts* of each real component:
  - sentiment polarity ordering (negative text < positive text)
  - stress score bounds and direction
  - trend detection on a synthetic rising series
  - safety detection on acute-distress phrasing
  - recommendation routing (safety-first; theme-aware)
  - the end-to-end pipeline + analytics via an in-memory SQLite app

Run:  pytest -q
They use a throwaway SQLite DB so they never touch a real database.
"""
import os
import datetime as dt

# Force a clean, isolated SQLite DB + no auto-seed for unit-level tests.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suite.db")
os.environ["SEED_ON_START"] = "false"

from app.nlp.sentiment import analyze_sentiment, stress_score
from app.nlp.keywords import extract_keywords, classify_themes
from app.ml.stress import analyze_trend
from app.services.safety import check_safety
from app.services.recommendations import recommend


# --------------------------------------------------------------------------- #
# NLP — sentiment & stress
# --------------------------------------------------------------------------- #
def test_sentiment_schema_and_polarity():
    neg = analyze_sentiment("I feel completely overwhelmed, exhausted and hopeless.")
    pos = analyze_sentiment("I feel calm, grateful and genuinely happy today.")
    for s in (neg, pos):
        assert set(s) == {"compound", "label", "pos", "neu", "neg"}
        assert -1.0 <= s["compound"] <= 1.0
    # Negative text must score lower than positive text.
    assert neg["compound"] < pos["compound"]
    assert neg["label"] == "negative"
    assert pos["label"] == "positive"


def test_stress_score_bounds_and_direction():
    neg_text = "Burned out, anxious, drowning in deadlines and no sleep."
    pos_text = "Relaxed weekend, slept well, feeling balanced and content."
    s_neg = stress_score(neg_text, analyze_sentiment(neg_text))
    s_pos = stress_score(pos_text, analyze_sentiment(pos_text))
    assert 0.0 <= s_pos <= 100.0
    assert 0.0 <= s_neg <= 100.0
    assert s_neg > s_pos


def test_keywords_and_themes():
    text = "Couldn't sleep again because of work deadlines and a fight with my friend."
    kws = extract_keywords(text)
    assert isinstance(kws, list) and len(kws) >= 1
    themes = classify_themes(text)
    # Should detect at least the sleep and/or work theme.
    assert {"sleep", "work"} & set(themes)


# --------------------------------------------------------------------------- #
# ML — trend detection
# --------------------------------------------------------------------------- #
def test_trend_detects_rising_series():
    today = dt.date.today()
    # 14 days of steadily climbing stress -> slope should be positive / "rising".
    entries = [
        {"date": today - dt.timedelta(days=13 - i),
         "stress": 20.0 + i * 4.0,
         "sentiment": 0.3 - i * 0.04}
        for i in range(14)
    ]
    report = analyze_trend(entries)
    assert report["trend"] == "rising"
    assert report["slope_per_day"] > 0
    assert report["series"]  # non-empty
    assert report["state"] in {"low", "moderate", "elevated", "high"}


def test_trend_handles_empty():
    report = analyze_trend([])
    assert report["trend"] == "stable"
    assert report["series"] == []


# --------------------------------------------------------------------------- #
# Safety layer
# --------------------------------------------------------------------------- #
def test_safety_flags_acute_distress():
    assert check_safety("I don't want to be here anymore, I can't go on.") is True


def test_safety_passes_ordinary_stress():
    assert check_safety("Work was stressful today but I'll be fine after a walk.") is False


# --------------------------------------------------------------------------- #
# Recommendations — routing
# --------------------------------------------------------------------------- #
def test_recommend_safety_first():
    recs = recommend(safety_flag=True, themes=["work"], trend="rising",
                     volatility=30.0, stress_level=90.0)
    assert len(recs) == 1
    assert recs[0]["category"] == "support"


def test_recommend_is_theme_aware():
    recs = recommend(safety_flag=False, themes=["sleep"], trend="rising",
                     volatility=10.0, stress_level=70.0)
    cats = {r["category"] for r in recs}
    assert "sleep" in cats
    # Every recommendation must carry an explainable rationale.
    assert all(r.get("rationale") for r in recs)


# --------------------------------------------------------------------------- #
# End-to-end — pipeline + analytics via the real app (in-memory-ish SQLite)
# --------------------------------------------------------------------------- #
def test_pipeline_and_analytics_end_to_end():
    # Uses the test DB configured at module import (test_suite.db), no reloads.
    import app.database as database
    import app.models as models
    database.init_db()

    from app.pipeline import process_entry
    db = database.SessionLocal()
    try:
        user = models.User(username="testuser", email="test@example.com",
                           cohort_week="2025-W01", persona="improving")
        db.add(user)
        db.commit()
        db.refresh(user)

        # Two contrasting entries run through the SAME real pipeline.
        out1 = process_entry(db, user.id,
                             "Swamped at work, barely slept, anxious about everything.")
        out2 = process_entry(db, user.id,
                             "Good day — finished early, went for a run, feeling calm.")

        assert out1["stress_score"] > out2["stress_score"]
        assert "trend" in out1 and "recommendations" in out1

        from app.services.analytics import overview
        ov = overview(db)
        assert ov["total_users"] >= 1
        assert "stickiness_dau_wau" in ov
    finally:
        db.close()
