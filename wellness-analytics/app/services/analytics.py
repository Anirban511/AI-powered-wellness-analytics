"""
Analytics — the business brain of the platform.

This module answers the questions an interviewer (or a buyer) actually asks:
  - Are people using it?            -> engagement / DAU-WAU-MAU, streaks
  - Do they stick around?           -> retention cohorts
  - Does the product loop close?    -> engagement funnel (journal -> insight -> act)
  - Does it *work*?                 -> wellbeing outcomes (% of users improving)
  - Is it worth money?              -> ROI model (revenue vs. value delivered)

Wellbeing outcomes are the bridge between "ML output" and "business value": a
corporate-wellness buyer pays for *outcomes and engagement*, not sentiment scores.
The ROI figures use explicit, overridable assumptions (see config.py) and are
clearly illustrative, not a promise.
"""
import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EngagementEvent, JournalEntry, Recommendation, User


def _events_df(db: Session) -> pd.DataFrame:
    rows = db.query(EngagementEvent.user_id, EngagementEvent.event_type,
                    EngagementEvent.created_at).all()
    if not rows:
        return pd.DataFrame(columns=["user_id", "event_type", "created_at"])
    df = pd.DataFrame(rows, columns=["user_id", "event_type", "created_at"])
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    return df


def _today(db: Session) -> dt.date:
    """Use the latest event date as 'now' so demo data always looks current."""
    latest = db.query(func.max(EngagementEvent.created_at)).scalar()
    return latest.date() if latest else dt.date.today()


# --------------------------------------------------------------------------- #
# Engagement overview
# --------------------------------------------------------------------------- #
def overview(db: Session) -> dict:
    today = _today(db)
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_entries = db.query(func.count(JournalEntry.id)).scalar() or 0

    df = _events_df(db)
    journaled = df[df.event_type == "journaled"] if not df.empty else df

    def active_since(days: int) -> int:
        if journaled.empty:
            return 0
        cutoff = today - dt.timedelta(days=days)
        return journaled[journaled.date > cutoff]["user_id"].nunique()

    wau = active_since(7)
    mau = active_since(30)
    dau = int(journaled[journaled.date == today]["user_id"].nunique()) if not journaled.empty else 0

    avg_entries = round(total_entries / total_users, 1) if total_users else 0.0
    stickiness = round(dau / wau, 2) if wau else 0.0  # DAU/WAU "stickiness"

    avg_stress = db.query(func.avg(JournalEntry.stress_score)).scalar()
    safety_flags = db.query(func.count(JournalEntry.id)).filter(JournalEntry.safety_flag.is_(True)).scalar()

    outcomes = wellbeing_outcomes(db)

    return {
        "as_of": today.isoformat(),
        "total_users": total_users,
        "total_entries": total_entries,
        "dau": dau, "wau": wau, "mau": mau,
        "stickiness_dau_wau": stickiness,
        "avg_entries_per_user": avg_entries,
        "avg_stress_score": round(float(avg_stress), 1) if avg_stress else 0.0,
        "safety_flags": int(safety_flags or 0),
        "pct_users_improving": outcomes["pct_improving"],
        "avg_stress_change": outcomes["avg_change"],
    }


# --------------------------------------------------------------------------- #
# Retention cohorts (by signup week)
# --------------------------------------------------------------------------- #
def retention_cohorts(db: Session, max_weeks: int = 8) -> dict:
    users = db.query(User.id, User.cohort_week).all()
    df_users = pd.DataFrame(users, columns=["user_id", "cohort_week"])
    events = _events_df(db)
    if df_users.empty or events.empty:
        return {"cohorts": [], "week_labels": []}

    events = events.merge(df_users, on="user_id", how="left")
    events["cohort_week"] = pd.to_datetime(events["cohort_week"])
    events["event_week"] = pd.to_datetime(events["date"]) - pd.to_timedelta(
        pd.to_datetime(events["date"]).dt.weekday, unit="D")
    events["week_offset"] = ((events["event_week"] - events["cohort_week"]).dt.days // 7)
    events = events[(events.week_offset >= 0) & (events.week_offset < max_weeks)]

    cohort_sizes = df_users.assign(cohort_week=pd.to_datetime(df_users.cohort_week)) \
        .groupby("cohort_week")["user_id"].nunique()

    table = (events.groupby(["cohort_week", "week_offset"])["user_id"].nunique()
             .reset_index())

    cohorts = []
    for cw in sorted(cohort_sizes.index):
        size = int(cohort_sizes[cw])
        row = {"cohort": cw.date().isoformat(), "size": size, "retention": []}
        for w in range(max_weeks):
            active = table[(table.cohort_week == cw) & (table.week_offset == w)]["user_id"]
            active = int(active.iloc[0]) if not active.empty else 0
            row["retention"].append(round(100 * active / size, 1) if size else 0.0)
        cohorts.append(row)

    return {"cohorts": cohorts, "week_labels": [f"W{w}" for w in range(max_weeks)]}


# --------------------------------------------------------------------------- #
# Engagement funnel
# --------------------------------------------------------------------------- #
def engagement_funnel(db: Session) -> dict:
    total = db.query(func.count(User.id)).scalar() or 0

    def users_with(event_type: str) -> int:
        return db.query(func.count(func.distinct(EngagementEvent.user_id))) \
            .filter(EngagementEvent.event_type == event_type).scalar() or 0

    journaled = users_with("journaled")
    viewed = users_with("viewed_dashboard")
    got_reco = db.query(func.count(func.distinct(Recommendation.user_id))).scalar() or 0
    accepted = db.query(func.count(func.distinct(Recommendation.user_id))) \
        .filter(Recommendation.accepted.is_(True)).scalar() or 0

    steps = [
        ("Signed up", total),
        ("Journaled", journaled),
        ("Viewed insights", viewed),
        ("Got a recommendation", got_reco),
        ("Acted on it", accepted),
    ]
    base = total or 1
    return {"steps": [{"name": n, "users": u, "pct": round(100 * u / base, 1)} for n, u in steps]}


# --------------------------------------------------------------------------- #
# Wellbeing outcomes — does the product actually help?
# --------------------------------------------------------------------------- #
def wellbeing_outcomes(db: Session) -> dict:
    rows = db.query(JournalEntry.user_id, JournalEntry.created_at,
                    JournalEntry.stress_score).all()
    if not rows:
        return {"pct_improving": 0.0, "avg_change": 0.0, "n_evaluated": 0}
    df = pd.DataFrame(rows, columns=["user_id", "created_at", "stress"])
    df["created_at"] = pd.to_datetime(df["created_at"])

    improving, changes = 0, []
    evaluated = 0
    for uid, g in df.groupby("user_id"):
        if len(g) < 6:           # need enough history to judge a trend
            continue
        g = g.sort_values("created_at")
        x = np.arange(len(g))
        slope = np.polyfit(x, g["stress"].values, 1)[0]  # stress change per entry
        first = g["stress"].iloc[: max(1, len(g)//3)].mean()
        last = g["stress"].iloc[-max(1, len(g)//3):].mean()
        changes.append(last - first)
        if slope < 0:
            improving += 1
        evaluated += 1

    pct = round(100 * improving / evaluated, 1) if evaluated else 0.0
    avg_change = round(float(np.mean(changes)), 1) if changes else 0.0
    return {"pct_improving": pct, "avg_change": avg_change, "n_evaluated": evaluated}


# --------------------------------------------------------------------------- #
# ROI model (illustrative, assumptions in config.py)
# --------------------------------------------------------------------------- #
def roi(db: Session, seats: int | None = None, price_per_seat: float | None = None) -> dict:
    total_users = db.query(func.count(User.id)).scalar() or 0
    seats = seats or max(total_users, 1)
    price = price_per_seat if price_per_seat is not None else settings.PRICE_PER_SEAT_MONTH

    outcomes = wellbeing_outcomes(db)
    funnel = engagement_funnel(db)
    engaged_pct = next((s["pct"] for s in funnel["steps"] if s["name"] == "Journaled"), 0.0) / 100

    mrr = seats * price
    arr = mrr * 12

    # Value delivered (illustrative): engaged users who improved -> fewer lost days.
    improved_users = seats * engaged_pct * (outcomes["pct_improving"] / 100)
    annual_value = (improved_users
                    * settings.ABSENCE_DAYS_SAVED_PER_IMPROVED_USER
                    * settings.AVG_LOADED_COST_PER_DAY)
    roi_multiple = round(annual_value / arr, 2) if arr else 0.0

    return {
        "seats": seats,
        "price_per_seat_month": price,
        "mrr": round(mrr, 2),
        "arr": round(arr, 2),
        "engaged_pct": round(engaged_pct * 100, 1),
        "pct_improving": outcomes["pct_improving"],
        "estimated_improved_users": round(improved_users, 1),
        "estimated_annual_value_delivered": round(annual_value, 2),
        "roi_multiple": roi_multiple,
        "assumptions": {
            "avg_loaded_cost_per_day": settings.AVG_LOADED_COST_PER_DAY,
            "absence_days_saved_per_improved_user": settings.ABSENCE_DAYS_SAVED_PER_IMPROVED_USER,
            "note": "Illustrative B2B corporate-wellness model. Value-delivered is a proxy "
                    "(engaged + improved users -> reduced absenteeism). Tune in config.py.",
        },
    }
