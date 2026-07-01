"""
Entry pipeline — the orchestration layer.

This is the single code path that turns raw journal text into stored signals and
personalised guidance. Both the live API and the demo seeder call it, so demo data
is produced by exactly the same logic users hit in production (no divergence).

    text -> sentiment -> stress score -> safety -> themes/keywords
         -> persist entry -> trend(history) -> recommendations -> events
"""
import datetime as dt

from sqlalchemy.orm import Session

from app.ml.stress import analyze_trend
from app.models import EngagementEvent, JournalEntry, Recommendation
from app.nlp.keywords import classify_themes, extract_keywords
from app.nlp.sentiment import analyze_sentiment, stress_score
from app.services.recommendations import recommend
from app.services.safety import check_safety


def _history(db: Session, user_id: int) -> list[dict]:
    rows = (db.query(JournalEntry.created_at, JournalEntry.stress_score,
                     JournalEntry.sentiment_compound)
            .filter(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.created_at).all())
    return [{"date": r[0].date(), "stress": r[1] or 0.0, "sentiment": r[2] or 0.0}
            for r in rows]


def process_entry(db: Session, user_id: int, text: str,
                  created_at: dt.datetime | None = None, log_events: bool = True,
                  commit: bool = True) -> dict:
    created_at = created_at or dt.datetime.now(dt.timezone.utc)

    sentiment = analyze_sentiment(text)
    stress = stress_score(text, sentiment)
    safety = check_safety(text)
    keywords = extract_keywords(text)
    themes = classify_themes(text)

    entry = JournalEntry(
        user_id=user_id, created_at=created_at, text=text,
        sentiment_compound=sentiment["compound"], sentiment_label=sentiment["label"],
        pos=sentiment["pos"], neu=sentiment["neu"], neg=sentiment["neg"],
        keywords=keywords, stress_score=stress, safety_flag=safety,
    )
    db.add(entry)
    db.flush()  # assign entry.id without committing yet

    # Trend uses full history INCLUDING this entry (already flushed).
    trend = analyze_trend(_history(db, user_id))

    recs = recommend(
        safety_flag=safety, themes=themes, trend=trend["trend"],
        volatility=trend["volatility"], stress_level=stress,
    )
    rec_objs = []
    for r in recs:
        obj = Recommendation(
            user_id=user_id, entry_id=entry.id, created_at=created_at,
            category=r["category"], title=r["title"], body=r["body"],
            rationale=r["rationale"], accepted=False,
        )
        db.add(obj)
        rec_objs.append(obj)

    if log_events:
        db.add(EngagementEvent(user_id=user_id, created_at=created_at,
                               event_type="journaled", meta={"stress": stress}))

    if commit:
        db.commit()
        db.refresh(entry)
        for o in rec_objs:
            db.refresh(o)
    else:
        db.flush()

    return {
        "id": entry.id, "user_id": user_id, "created_at": entry.created_at,
        "text": text,
        "sentiment": {**sentiment, "keywords": keywords},
        "stress_score": stress, "safety_flag": safety,
        "themes": themes,
        "trend": trend,
        "recommendations": [
            {"id": o.id, "category": o.category, "title": o.title,
             "body": o.body, "rationale": o.rationale, "accepted": o.accepted}
            for o in rec_objs
        ],
    }
