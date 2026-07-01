"""
FastAPI application — the backend that wires the whole platform together.

Routes group into three surfaces:
  - Pages   : /            (dashboard)   /report/{id} (printable weekly report)
  - Pipeline: /api/entries, /api/users/{id}/trends, /recommendations/.../accept
  - Analytics: /api/analytics/*  (overview, retention, funnel, roi)

On startup we create tables and (optionally) seed reproducible demo data so the
dashboard is never empty for a reviewer.
"""
import datetime as dt
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import EngagementEvent, JournalEntry, Recommendation, User
from app.pipeline import process_entry
from app.schemas import EntryIn
from app.services import analytics
from app.services.reports import build_weekly_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title=settings.APP_NAME, version="1.0.0")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "..", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("startup")
def _startup():
    init_db()
    if settings.SEED_ON_START:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            if (db.query(func.count(User.id)).scalar() or 0) == 0:
                from scripts.seed_data import seed
                seed(db)
        finally:
            db.close()


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html",
                                       {"app_name": settings.APP_NAME})


@app.get("/report/{user_id}", response_class=HTMLResponse)
def report_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    report = build_weekly_report(db, user_id)
    return templates.TemplateResponse(request, "report.html", {"r": report})


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return [{"id": u.id, "username": u.username,
             "persona": u.persona, "cohort_week": u.cohort_week} for u in users]


# --------------------------------------------------------------------------- #
# Journal pipeline
# --------------------------------------------------------------------------- #
@app.post("/api/entries")
def create_entry(payload: EntryIn, db: Session = Depends(get_db)):
    if not db.query(User).get(payload.user_id):
        raise HTTPException(404, "user not found")
    return process_entry(db, payload.user_id, payload.text)


@app.get("/api/users/{user_id}/entries")
def user_entries(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(JournalEntry).filter(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.created_at.desc()).limit(limit).all())
    return [{"id": e.id, "created_at": e.created_at, "text": e.text,
             "stress_score": e.stress_score, "sentiment_label": e.sentiment_label,
             "sentiment_compound": e.sentiment_compound, "keywords": e.keywords,
             "safety_flag": e.safety_flag} for e in rows]


@app.get("/api/users/{user_id}/trends")
def user_trends(user_id: int, db: Session = Depends(get_db)):
    from app.ml.stress import analyze_trend
    rows = (db.query(JournalEntry.created_at, JournalEntry.stress_score,
                     JournalEntry.sentiment_compound)
            .filter(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.created_at).all())
    hist = [{"date": r[0].date(), "stress": r[1] or 0.0, "sentiment": r[2] or 0.0} for r in rows]
    # log the dashboard view for the engagement funnel
    db.add(EngagementEvent(user_id=user_id, event_type="viewed_dashboard", meta={}))
    db.commit()
    return {"user_id": user_id, **analyze_trend(hist)}


@app.get("/api/users/{user_id}/recommendations")
def user_recs(user_id: int, limit: int = 10, db: Session = Depends(get_db)):
    rows = (db.query(Recommendation).filter(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc()).limit(limit).all())
    return [{"id": r.id, "category": r.category, "title": r.title, "body": r.body,
             "rationale": r.rationale, "accepted": r.accepted,
             "created_at": r.created_at} for r in rows]


@app.post("/api/recommendations/{rec_id}/accept")
def accept_rec(rec_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).get(rec_id)
    if not rec:
        raise HTTPException(404, "recommendation not found")
    rec.accepted = True
    db.add(EngagementEvent(user_id=rec.user_id, event_type="accepted_reco",
                           meta={"rec_id": rec_id}))
    db.commit()
    return {"id": rec_id, "accepted": True}


# --------------------------------------------------------------------------- #
# Weekly report (JSON)
# --------------------------------------------------------------------------- #
@app.get("/api/users/{user_id}/report")
def weekly_report(user_id: int, db: Session = Depends(get_db)):
    db.add(EngagementEvent(user_id=user_id, event_type="viewed_report", meta={}))
    db.commit()
    return build_weekly_report(db, user_id)


# --------------------------------------------------------------------------- #
# Analytics (business surface)
# --------------------------------------------------------------------------- #
@app.get("/api/analytics/overview")
def analytics_overview(db: Session = Depends(get_db)):
    return analytics.overview(db)


@app.get("/api/analytics/retention")
def analytics_retention(db: Session = Depends(get_db)):
    return analytics.retention_cohorts(db)


@app.get("/api/analytics/funnel")
def analytics_funnel(db: Session = Depends(get_db)):
    return analytics.engagement_funnel(db)


@app.get("/api/analytics/roi")
def analytics_roi(seats: int | None = None, price: float | None = None,
                  db: Session = Depends(get_db)):
    return analytics.roi(db, seats=seats, price_per_seat=price)
