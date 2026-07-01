"""
Demo data seeder — SYNTHETIC data, real pipeline.

Everything below is generated, not real user data. It exists so a reviewer opening
the dashboard sees a living product instead of an empty shell. Crucially, each
synthetic entry is pushed through the SAME `process_entry` pipeline the live API
uses, so the sentiment scores, stress levels, and recommendations are genuinely
computed by the system — only the journal *text* is templated.

Personas create distinct, legible trajectories an analyst can reason about:
  improving | worsening | stable_stressed | stable_calm | sporadic
"""
import datetime as dt
import random

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EngagementEvent, Recommendation, User
from app.pipeline import process_entry

# --- Templated sentence pools (valence-tagged) ---------------------------------
POS = [
    "Had a genuinely good day and felt grateful for the small wins.",
    "Felt calm and focused; things are finally clicking into place.",
    "Caught up with a friend and it lifted my mood completely.",
    "Proud of myself for finishing what I set out to do today.",
    "Slept well and woke up feeling relaxed and hopeful.",
    "A peaceful, steady day — nothing dramatic, just content.",
    "Went for a walk and came back feeling lighter and happy.",
]
NEU = [
    "An ordinary day, nothing much stood out either way.",
    "Got through the usual tasks; mood was pretty neutral.",
    "Quiet day at home, just ticking things off the list.",
    "Fairly average day, neither good nor bad really.",
]
NEG = [
    "Felt overwhelmed by deadlines and couldn't switch off.",
    "Exhausted and anxious; the workload is piling up and I'm behind.",
    "Stressed about money and bills again, it's wearing me down.",
    "Had an argument with a friend and it's been on my mind all day.",
    "Couldn't sleep, the pressure of the exam is getting to me.",
    "Burnt out and tired, everything feels like too much right now.",
    "Frustrated and tense; too many meetings and no time to think.",
]

PERSONAS = ["improving", "worsening", "stable_stressed", "stable_calm", "sporadic"]


def _valence_for(persona: str, t: float) -> float:
    """t in [0,1] across the user's lifetime -> target valence in [-1,1]."""
    if persona == "improving":
        return -0.6 + 1.2 * t           # starts low, climbs
    if persona == "worsening":
        return 0.5 - 1.1 * t            # starts ok, declines
    if persona == "stable_stressed":
        return -0.4
    if persona == "stable_calm":
        return 0.55
    return random.uniform(-0.5, 0.6)    # sporadic -> noisy


def _compose(valence: float) -> str:
    """Pick sentences whose tone matches the target valence (+ noise)."""
    v = max(-1.0, min(1.0, valence + random.uniform(-0.2, 0.2)))
    if v > 0.2:
        pool, extra = POS, POS
    elif v < -0.2:
        pool, extra = NEG, NEG
    else:
        pool, extra = NEU, (POS if random.random() > 0.5 else NEG)
    n = random.choice([1, 2, 2, 3])
    return " ".join(random.sample(pool + extra, k=min(n, len(pool + extra))))


def _journals_per_week(persona: str) -> int:
    return {"improving": 5, "worsening": 4, "stable_stressed": 4,
            "stable_calm": 5, "sporadic": 2}[persona]


def seed(db: Session) -> dict:
    random.seed(settings.SEED_SEED)
    n_users = settings.SEED_USERS
    weeks = settings.SEED_WEEKS
    today = dt.date.today()
    period_end = today

    created_users = 0
    created_entries = 0

    for i in range(1, n_users + 1):
        persona = PERSONAS[i % len(PERSONAS)]
        # Spread signups across the first `weeks-1` weeks for retention cohorts.
        signup_offset_weeks = random.randint(0, max(weeks - 2, 0))
        signup = period_end - dt.timedelta(weeks=(weeks - 1 - signup_offset_weeks))
        cohort_monday = signup - dt.timedelta(days=signup.weekday())

        user = User(
            username=f"user{i:03d}", email=f"user{i:03d}@demo.aura",
            created_at=dt.datetime.combine(signup, dt.time(9, 0)),
            cohort_week=cohort_monday.isoformat(), persona=persona,
        )
        db.add(user)
        db.flush()
        created_users += 1

        # Sporadic users may churn: stop journaling partway through.
        lifetime_days = (period_end - signup).days
        if persona == "sporadic" and random.random() < 0.5:
            lifetime_days = int(lifetime_days * random.uniform(0.3, 0.7))

        jpw = _journals_per_week(persona)
        day = signup
        end = signup + dt.timedelta(days=lifetime_days)
        while day <= end:
            # journal on a random subset of days matching the weekly cadence
            if random.random() < jpw / 7.0:
                t = (day - signup).days / max(lifetime_days, 1)
                valence = _valence_for(persona, t)
                # weekdays skew slightly more stressed
                if day.weekday() < 5:
                    valence -= 0.1
                text = _compose(valence)
                ts = dt.datetime.combine(day, dt.time(random.randint(7, 22), random.randint(0, 59)))
                process_entry(db, user.id, text, created_at=ts, log_events=True, commit=False)
                created_entries += 1
            day += dt.timedelta(days=1)

        db.commit()  # one commit per user (fast + transactional)

        # --- Simulate downstream engagement funnel events ---
        # Most active users view the dashboard; fewer view reports; some act on advice.
        _simulate_funnel(db, user, persona, end)

    db.commit()
    return {"users": created_users, "entries": created_entries}


def _simulate_funnel(db: Session, user: User, persona: str, last_active: dt.date):
    rng = random.random
    # viewed_dashboard
    if persona != "sporadic" or rng() < 0.6:
        for _ in range(random.randint(1, 6)):
            d = last_active - dt.timedelta(days=random.randint(0, 14))
            db.add(EngagementEvent(user_id=user.id, event_type="viewed_dashboard",
                                   created_at=dt.datetime.combine(d, dt.time(20, 0)), meta={}))
    # viewed_report
    if rng() < (0.55 if persona != "sporadic" else 0.2):
        db.add(EngagementEvent(user_id=user.id, event_type="viewed_report",
                               created_at=dt.datetime.combine(last_active, dt.time(9, 0)), meta={}))
    # accepted a recommendation
    recs = db.query(Recommendation).filter(Recommendation.user_id == user.id).all()
    if recs and rng() < (0.45 if persona != "sporadic" else 0.15):
        chosen = random.choice(recs)
        chosen.accepted = True
        db.add(EngagementEvent(user_id=user.id, event_type="accepted_reco",
                               created_at=chosen.created_at, meta={"rec_id": chosen.id}))
    db.commit()


if __name__ == "__main__":
    from app.database import SessionLocal, init_db
    init_db()
    s = SessionLocal()
    try:
        result = seed(s)
        print(f"Seeded: {result}")
    finally:
        s.close()
