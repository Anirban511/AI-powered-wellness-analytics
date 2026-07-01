"""
Weekly reports.

Aggregates one user's week into the kind of digest a person would actually want
in their inbox on Monday morning: where stress landed, what drove it, how it
compares to last week, and the single most useful next step.

Returns plain dicts so the same payload powers the JSON API and the HTML report.
"""
import datetime as dt
from collections import Counter

import numpy as np
from sqlalchemy.orm import Session

from app.models import JournalEntry, User


def _week_bounds(ref: dt.date) -> tuple[dt.date, dt.date]:
    """Monday..Sunday containing `ref`."""
    monday = ref - dt.timedelta(days=ref.weekday())
    return monday, monday + dt.timedelta(days=6)


def _entries_between(db: Session, user_id: int, start: dt.date, end: dt.date):
    return (db.query(JournalEntry)
            .filter(JournalEntry.user_id == user_id)
            .filter(JournalEntry.created_at >= dt.datetime.combine(start, dt.time.min))
            .filter(JournalEntry.created_at <= dt.datetime.combine(end, dt.time.max))
            .order_by(JournalEntry.created_at).all())


def build_weekly_report(db: Session, user_id: int, ref_date: dt.date | None = None) -> dict:
    user = db.query(User).get(user_id)
    if not user:
        return {"error": "user not found"}

    # Anchor to the user's latest entry so demo reports are never empty.
    if ref_date is None:
        latest = (db.query(JournalEntry.created_at)
                  .filter(JournalEntry.user_id == user_id)
                  .order_by(JournalEntry.created_at.desc()).first())
        ref_date = latest[0].date() if latest else dt.date.today()

    start, end = _week_bounds(ref_date)
    this_week = _entries_between(db, user_id, start, end)
    prev_start, prev_end = start - dt.timedelta(days=7), start - dt.timedelta(days=1)
    last_week = _entries_between(db, user_id, prev_start, prev_end)

    if not this_week:
        return {"user": user.username, "week_start": start.isoformat(),
                "week_end": end.isoformat(), "entries": 0,
                "narrative": "No entries this week — a fresh start is one journal away."}

    stress = np.array([e.stress_score for e in this_week], dtype=float)
    avg_stress = round(float(np.mean(stress)), 1)
    prev_avg = round(float(np.mean([e.stress_score for e in last_week])), 1) if last_week else None
    delta = round(avg_stress - prev_avg, 1) if prev_avg is not None else None

    best = min(this_week, key=lambda e: e.stress_score)
    worst = max(this_week, key=lambda e: e.stress_score)

    kw = Counter()
    for e in this_week:
        kw.update(e.keywords or [])
    top_keywords = [w for w, _ in kw.most_common(6)]

    labels = Counter(e.sentiment_label for e in this_week)
    dominant_mood = labels.most_common(1)[0][0] if labels else "neutral"

    narrative = _narrative(user.username, avg_stress, delta, dominant_mood, top_keywords)

    return {
        "user": user.username,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "entries": len(this_week),
        "avg_stress": avg_stress,
        "prev_week_avg_stress": prev_avg,
        "delta_vs_last_week": delta,
        "dominant_mood": dominant_mood,
        "mood_breakdown": dict(labels),
        "best_day": {"date": best.created_at.date().isoformat(), "stress": best.stress_score},
        "worst_day": {"date": worst.created_at.date().isoformat(), "stress": worst.stress_score},
        "top_themes": top_keywords,
        "narrative": narrative,
    }


def _narrative(name, avg, delta, mood, keywords) -> str:
    parts = [f"This week averaged a stress level of {avg}/100, with a mostly {mood} tone."]
    if delta is not None:
        if delta <= -3:
            parts.append(f"That's down {abs(delta)} points from last week — real progress.")
        elif delta >= 3:
            parts.append(f"That's up {delta} points from last week, worth keeping an eye on.")
        else:
            parts.append("That's about the same as last week.")
    if keywords:
        parts.append(f"Recurring themes: {', '.join(keywords[:4])}.")
    return " ".join(parts)
