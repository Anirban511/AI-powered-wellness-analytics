# Aura — AI-Powered Wellness Analytics Platform
### Project Guide & Interview Companion

Aura is a full-stack, B2B corporate-wellness analytics product. An employee keeps a short
**mood journal**; Aura runs each entry through an **NLP + ML pipeline** to score sentiment and
stress, detects **stress trends** over time, generates **personalized, explainable
recommendations**, and rolls everything up into a **dashboard**, **weekly reports**, and
**business-facing user-analytics** (engagement, retention, funnel, and an ROI model an
interviewer or a buyer can play with).

It is deliberately built to demonstrate the *integration* of NLP, ML, backend, frontend,
database, product thinking, business metrics, and engagement analysis in one coherent system —
not seven disconnected scripts.

> **One honest sentence up front:** the *engineering* is real and runs live (NLP, stress model,
> trend detection, analytics math, the whole web app). The *demo dataset* is synthetic but flows
> through the exact same pipeline as real input, and the *ROI dollar figures* are an explicitly
> illustrative, fully configurable model — not a measured clinical claim. The "What's real vs.
> synthetic vs. illustrative" section spells this out precisely.

---

## 1. The pipeline (the spec, implemented)

```
Mood Journal  →  Sentiment Analysis  →  Stress Trend Detection  →  Personalized
Recommendations  →  Dashboard  →  Weekly Reports  →  User Analytics
```

Every arrow is a real module. Here is where each stage lives:

| Stage | What happens | Code |
|---|---|---|
| **Mood Journal** | Free-text entry captured + persisted with timestamp | `POST /api/entries`, `models.JournalEntry` |
| **Sentiment Analysis** | Text → `{compound, label, pos, neu, neg}` on a unified [-1,1] scale | `app/nlp/sentiment.py` |
| **Stress scoring** | Composite 0–100 stress from sentiment + stressor lexicon | `stress_score()` in `app/nlp/sentiment.py` |
| **Stress Trend Detection** | Daily series → EWMA smoothing → linear-regression slope → state, volatility, anomalies, forecast | `app/ml/stress.py` |
| **Personalized Recommendations** | Safety-first, trend-aware, theme-aware, *explainable* suggestions | `app/services/recommendations.py` |
| **Dashboard** | "Me" view (personal) + "Business" view (analytics), Chart.js | `app/templates/dashboard.html`, `static/dashboard.js` |
| **Weekly Reports** | Printable Mon–Sun summary with narrative + deltas | `app/services/reports.py`, `app/templates/report.html` |
| **User Analytics** | DAU/WAU/MAU, stickiness, retention cohorts, engagement funnel, outcomes, ROI | `app/services/analytics.py` |

The orchestrator that ties stages 1–5 together for a single entry is **`app/pipeline.py →
process_entry()`**. This matters for interviews: a recruiter can ask "walk me through one
journal entry" and the answer is a single function call chain, not hand-waving.

---

## 2. Architecture at a glance

```
                        ┌──────────────────────────────────────────────┐
  Browser  ──HTTP──▶    │  FastAPI (app/main.py)                        │
  (Chart.js, vanilla JS)│   ├─ Pages: / (dashboard), /report/{id}       │
                        │   └─ JSON API: /api/entries, /api/users,      │
                        │        /api/users/{id}/trends|recos|report,   │
                        │        /api/analytics/{overview,retention,    │
                        │                        funnel,roi}            │
                        └───────────────┬──────────────────────────────┘
                                        │
            ┌───────────────────────────┼─────────────────────────────┐
            ▼                           ▼                             ▼
     NLP (app/nlp)              ML (app/ml/stress.py)        Services (app/services)
   sentiment.py  keywords.py    EWMA + LinearRegression      safety, recommendations,
   VADER / transformer          slope / anomalies / forecast analytics, reports
            │                           │                             │
            └───────────────┬───────────┴──────────────┬─────────────┘
                            ▼                          ▼
                   pipeline.py (orchestration)   SQLAlchemy ORM (app/models.py)
                                                  Users / JournalEntries /
                                                  Recommendations / EngagementEvents
                                                  → SQLite (local) | Postgres (Docker)
```

**Design principles**
- **DB-agnostic.** Same code, SQLite locally (zero setup) and Postgres in Docker — only
  `DATABASE_URL` changes.
- **Pluggable NLP.** VADER by default (fast, deterministic, no downloads); flip
  `SENTIMENT_BACKEND=transformer` to swap in a HuggingFace model behind the *same* interface.
- **Explainability everywhere.** Every recommendation carries a `rationale`; every trend a
  `summary`. Nothing is a black box the user can't interrogate.
- **Config as contract.** All tunables — including the business assumptions — live in
  `app/config.py` and are env-overridable, so the analytics are auditable, not buried.

---

## 3. Layer-by-layer

### 3.1 NLP (`app/nlp/`)
- **`sentiment.py`** — `analyze_sentiment()` returns a backend-agnostic dict
  `{compound, label, pos, neu, neg}` with `compound ∈ [-1, 1]`. The transformer path maps
  POSITIVE/NEGATIVE probability onto the same signed scale so downstream code never knows or
  cares which backend ran. `stress_score()` is a transparent composite in **[0, 100]**:
  `0.62·(negativity from compound) + 0.30·neg + stressor-keyword boost`. The weights are
  explicit so you can defend every number.
- **`keywords.py`** — frequency-based keyword extraction (stop-word filtered, apostrophe-aware
  tokenizer) plus `classify_themes()` against a `THEME_LEXICON` (sleep / work / social / money /
  health / positive). Themes are what make recommendations feel personal.

### 3.2 ML — trend detection (`app/ml/stress.py`)
`analyze_trend(entries)` is the analytical heart:
1. **Daily aggregation** — collapse multiple entries/day to a daily mean stress series.
2. **EWMA smoothing** (α = 0.4) — denoise day-to-day spikes so the signal is readable.
3. **Linear regression** (`sklearn.LinearRegression`) over the last 14 days → **slope per day** →
   classified `rising` / `falling` / `stable`.
4. **Volatility** — std-dev of the recent series (instability matters as much as level).
5. **Anomaly detection** — z-score flags (|z| ≥ 1.8) mark unusually bad/good days.
6. **Forecast** — ~1-week linear projection of where stress is heading.
7. **State** — `low / moderate / elevated / high`, plus a plain-English `summary`.

It **degrades gracefully**: with one or two entries it returns a sane "not enough data yet"
report instead of throwing.

### 3.3 Services (`app/services/`)
- **`safety.py`** — a conservative, keyword-based acute-distress check. When it fires, the system
  **suppresses analytics/gamification** and surfaces a single supportive "reach out to a human /
  professional" message. It enumerates **no** self-harm methods and is wrapped in non-clinical
  disclaimers. This is the *product-thinking* and *responsible-AI* centerpiece.
- **`recommendations.py`** — `recommend()` routes **safety-first → trend → themes →
  reinforcement**, each with a human-readable `rationale`. Curated, non-clinical library
  (breathing, sleep hygiene, boundary-setting, reframing, social reach-out, positive
  reinforcement).
- **`analytics.py`** — the business brain (see §5).
- **`reports.py`** — `build_weekly_report()` produces a Mon–Sun summary anchored to the user's
  latest entry: average stress, **delta vs. previous week**, best/worst day, top themes, dominant
  mood, and a narrative.

### 3.4 Backend (`app/main.py`, `app/pipeline.py`)
FastAPI with a startup hook that **creates tables and seeds reproducible demo data if the DB is
empty** — this is what makes "one command and it just works" possible. `process_entry()`
orchestrates the full single-entry path: sentiment → stress → safety → keywords/themes → persist
→ trend(full history) → recommendations → log engagement event.

### 3.5 Database (`app/models.py`, `app/database.py`)
Four tables, indexed for the queries the analytics layer actually runs:
- **User** — `username`, `email`, `created_at`, `cohort_week` (for retention), `persona` (demo).
- **JournalEntry** — text + all NLP outputs + `stress_score` + `safety_flag` + `keywords` (JSON).
- **Recommendation** — `category / title / body / rationale / accepted` (acceptance = a measurable
  engagement signal).
- **EngagementEvent** — typed event log (`signed_up`, `journaled`, `viewed_dashboard`,
  `viewed_report`, `accepted_reco`) — the raw material for funnel + retention.

### 3.6 Frontend (`app/templates/`, `static/`)
Vanilla HTML + Chart.js served directly by FastAPI — **no Node build step**, so the whole thing
ships in one container. Two views:
- **"Me"** — journal box with live analysis (sentiment chips + stress gauge + instant recos), the
  signature **"mood ribbon"** (gradient stress timeline + EWMA line + anomaly dots), trend metrics,
  standing recommendations.
- **"Business"** — six KPI cards, the engagement funnel, a retention cohort heatmap, and an
  **interactive ROI calculator** (edit seats/price, watch the model recompute).

Design system (from a journal metaphor): Newsreader serif display + Inter body; calm cool palette
with sage = positive, amber = caution, coral = stress.

---

## 4. Product thinking

- **Who it's for:** an HR / People team buys Aura per-seat; employees get a private wellbeing
  tool, the company gets *aggregate, anonymized* trends — never a surveillance dashboard of
  individuals. (The "Business" view is cohort-level by construction.)
- **Safety over engagement:** the one place the product deliberately *reduces* engagement is acute
  distress — it stops nudging and points to human help. That trade-off is the credibility test for
  any wellness product.
- **Explainability as a feature:** users are far more likely to trust (and act on) a
  recommendation that says *why* it appeared. Every reco shows its rationale.
- **Leading vs. lagging indicators:** engagement (journaling cadence, reco acceptance) is the
  *leading* indicator of both user wellbeing improvement and B2B renewal — which is exactly why the
  analytics layer tracks it as carefully as the wellbeing outcomes.

---

## 5. Business metrics & user-engagement analysis (`app/services/analytics.py`)

This is the layer that lets an interviewer "generate insights about how the project fits business
profits." Four endpoints:

**`/api/analytics/overview`** — `total_users`, `total_entries`, **DAU / WAU / MAU**,
**stickiness (DAU/WAU)**, avg entries/user, avg stress score, safety-flag count, and
**% users improving** + avg stress change. (Uses the latest event date as "now" so the demo
always looks live.)

**`/api/analytics/retention`** — cohorts by signup week → a retention heatmap (do users keep
coming back?). Built with pandas.

**`/api/analytics/funnel`** — the engagement funnel:
`Signed up → Journaled → Viewed insights → Got a recommendation → Acted on it`. Each drop-off is a
product lever.

**`/api/analytics/roi`** — the **business-profit model** (illustrative, configurable):

```
MRR  = seats × price_per_seat_month
ARR  = MRR × 12
improved_users        = seats × engaged% × pct_improving%
annual_value_delivered= improved_users × absence_days_saved × loaded_cost_per_day
roi_multiple          = annual_value_delivered ÷ ARR
```

Example with demo defaults (45 seats, $6/seat/mo) it returns an ROI multiple around **3.5×** — i.e.
"for every $1 of subscription, the model estimates ~$3.50 of avoided absenteeism cost," *given the
stated assumptions*. Every assumption (`PRICE_PER_SEAT_MONTH`, `AVG_LOADED_COST_PER_DAY`,
`ABSENCE_DAYS_SAVED_PER_IMPROVED_USER`, churn baseline) lives in `config.py` and is editable live
in the dashboard. The interviewer can plug in a real prospect's numbers and watch the case change.

**Why this framing wins a renewal:** the value-delivered proxy is driven by *engaged + improved*
users, so it mechanically ties the thing the product optimizes (engagement → wellbeing) to the
thing the buyer renews on (demonstrable ROI). That's the whole product thesis in one equation.

---

## 6. What's real vs. synthetic vs. illustrative  *(read this before any interview)*

**100% real and running live:**
- The NLP pipeline (VADER sentiment, stress composite, keyword/theme extraction).
- The ML trend detection (EWMA, sklearn linear regression slope, volatility, z-score anomalies,
  forecast).
- The safety layer, the recommendation routing, and **every analytics computation** (DAU/WAU/MAU,
  stickiness, retention cohorts, funnel, outcomes, ROI math).
- The full web app: FastAPI backend, database layer, dashboard, weekly reports.
- When you type a brand-new journal entry in the live app, it runs through this exact pipeline.

**Synthetic (clearly labeled):**
- The **demo dataset** — `scripts/seed_data.py` generates ~45 users across 5 behavioral personas
  (improving / worsening / stable-stressed / stable-calm / sporadic) over 8 weeks. Only the
  *journal text* is templated from valence-tagged sentence pools; **every synthetic entry is run
  through the same real `process_entry()` pipeline** as live input. The seed is RNG-fixed
  (`SEED_SEED=7`) so demos are reproducible. Personas exist so retention cohorts and the funnel have
  realistic shape to show.

**Validated against real, public, labeled data — not synthetic (`validation/`):**
- The synthetic seed data is good for pipeline development but says nothing about whether the
  scoring logic is *correct*. `validation/run_real_data_validation.py` answers that by importing
  `analyze_sentiment()` and `stress_score()` **directly from `app/nlp/sentiment.py`** — the exact
  functions the live app calls — and running them against the public **Sentiment Analysis for
  Mental Health** dataset (Kaggle, suchintikasarkar): **52,681** real, human-labeled statements
  across 7 severity categories.
- Result: mean stress score for **Suicidal + Depression**-labeled text is **52.2**, versus **30.9**
  for **Normal**-labeled text — a **21.3-point separation**, produced by a function that never sees
  the label. Only **6.7%** of Normal-labeled text crosses a high-stress (≥60) threshold, versus
  **57.0%** of Suicidal-labeled text. Processed at **927** statements/second.
- This is genuine external evidence the unsupervised scoring tracks real severity — see
  `validation/README.md` for the full breakdown and how to reproduce it
  (`python validation/download_dataset.py && python validation/run_real_data_validation.py`).
- Scope, stated honestly: this validates *signal direction*, not classifier accuracy —
  `stress_score()` is a continuous unsupervised score, not a 7-way classifier, so
  precision/recall against these labels isn't the right frame. It also isn't a clinical validation;
  these are real social-media statements, not equivalent to a clinical mood journal.

**Illustrative (a model, not a measurement):**
- The **ROI dollar figures**. The *math* is real and runs on real (synthetic-sourced) engagement
  numbers, but the **assumptions** (cost per absence day, days saved per improved user) are
  industry-style placeholders, not a clinical trial result. They are explicit, configurable, and
  labeled as illustrative in the API response itself (`assumptions.note`).

If asked "is this production-ready?": the architecture is, the *clinical validity is not claimed* —
Aura is a wellbeing-support and analytics tool with non-clinical disclaimers, not a medical device.
Being able to say that crisply is the point.

---

## 7. Running it

### One command (Docker — full stack with Postgres)
```bash
docker compose up --build
```
Brings up Postgres + the API together; the API waits for the DB, creates tables, seeds the demo
data, and serves the dashboard. Open **http://localhost:8000**.

### One command (local, no Docker — SQLite, zero DB setup)
```bash
./run.sh
```
Creates a venv, installs deps, launches the app (auto-creates tables + seeds on first run). Open
**http://localhost:8000**.

### Tests
```bash
pytest -q
```
10 tests covering sentiment polarity, stress bounds, theme detection, rising-trend detection,
the safety layer, recommendation routing, and a full pipeline-plus-analytics end-to-end run.

### Useful endpoints
`/` dashboard · `/report/{user_id}` weekly report · `/health` · `/api/users` ·
`/api/analytics/overview|retention|funnel|roi`

---

## 8. Interview Q&A — talking points

**"Walk me through what happens to one journal entry."**
`POST /api/entries` → `process_entry()` runs sentiment → 0–100 stress composite → safety check →
keyword/theme extraction → persists the entry → recomputes the trend over full history → generates
explainable recommendations → logs an engagement event → returns everything to the UI for instant
display. One function, the whole pipeline.

**"How does stress trend detection actually work?"**
Daily-mean series → EWMA smoothing (α=0.4) to denoise → `sklearn.LinearRegression` over the last
14 days for a slope (rising/falling/stable) → std-dev volatility → z-score anomalies (|z|≥1.8) →
a short linear forecast → a low/moderate/elevated/high state with a plain-English summary. It
degrades gracefully when data is sparse.

**"Why VADER and not a big transformer?"**
Default is VADER: deterministic, no downloads, fast, easy to defend in a demo. But the backend is
pluggable behind one interface — `SENTIMENT_BACKEND=transformer` swaps in HuggingFace DistilBERT
returning the *same* schema. I optimized for a reproducible demo while keeping the upgrade path
one env var away.

**"How would this make a company money?"**
It's sold per-seat (MRR/ARR). The engagement funnel and retention cohorts are the leading
indicators of renewal; the ROI model ties engaged-and-improved users to avoided absenteeism cost.
The ROI multiple (~3.5× on demo defaults) is configurable so a buyer can plug in their own numbers
— and the model is structured so the thing we optimize (engagement → wellbeing) is the thing they
renew on.

**"What's real here and what isn't?"** → §6. Lead with this; it's a credibility multiplier.

**"Is your data real or synthetic?"**
Both, for different purposes. The demo dashboard uses reproducible synthetic data so the full
pipeline, dashboard, and analytics layer can be developed and shown without needing real personal
journal data. But the scoring logic itself is separately validated against a real, public, labeled
dataset — 52,681 real statements from Kaggle's "Sentiment Analysis for Mental Health" — by
importing the exact same `analyze_sentiment()`/`stress_score()` functions the app uses. That
validation shows a 21.3-point real separation between human-labeled high-risk and normal text,
which is the answer to "does this actually work," independent of the demo data.

**"What's the highest-ROI next step?"**
Replace the VADER default with a fine-tuned transformer and validate stress scores against a
labeled dataset to report a real correlation metric; add auth + per-tenant isolation for true
multi-tenancy; and instrument a real A/B test on recommendation acceptance to move the funnel's
"Acted on it" step.

**"Where's the responsible-AI thinking?"**
The safety layer is the clearest example: it's the one place the product deliberately *reduces*
engagement, suppressing nudges and pointing to human help on acute-distress signals, with no
method content and non-clinical disclaimers throughout.

---

## 9. File map

```
wellness-analytics/
├─ app/
│  ├─ main.py            FastAPI app, routes, startup seed hook
│  ├─ pipeline.py        process_entry() — single-entry orchestration
│  ├─ config.py          all tunables + business assumptions (env-overridable)
│  ├─ database.py        SQLAlchemy engine/session, init_db()
│  ├─ models.py          User / JournalEntry / Recommendation / EngagementEvent
│  ├─ schemas.py         Pydantic request/response models
│  ├─ nlp/
│  │  ├─ sentiment.py    analyze_sentiment() + stress_score()
│  │  └─ keywords.py     keyword extraction + theme classification
│  ├─ ml/
│  │  └─ stress.py       analyze_trend() — EWMA + regression + anomalies + forecast
│  ├─ services/
│  │  ├─ safety.py       acute-distress detection + support message
│  │  ├─ recommendations.py  safety-first, explainable recommender
│  │  ├─ analytics.py    overview / retention / funnel / outcomes / roi
│  │  └─ reports.py      weekly report builder
│  └─ templates/         dashboard.html, report.html
├─ static/               styles.css, dashboard.js (Chart.js mood ribbon, KPIs, funnel, ROI)
├─ scripts/seed_data.py  reproducible synthetic demo data (real pipeline, templated text)
├─ tests/test_pipeline.py  10 sanity + e2e tests
├─ validation/            real-data benchmark (imports the actual app.nlp.sentiment functions)
│  ├─ download_dataset.py       fetches + caches the public Kaggle dataset
│  ├─ run_real_data_validation.py  runs the real pipeline against it, prints + saves results
│  ├─ test_real_data_validation.py optional pytest, skipped if dataset isn't downloaded
│  └─ README.md            full results table + reproduction steps
├─ requirements.txt      pinned, tested deps
├─ Dockerfile            python:3.12-slim app image
├─ docker-compose.yml    Postgres + web, one-command stack
├─ entrypoint.sh         wait-for-db then launch uvicorn
├─ run.sh                local no-Docker one-command runner
└─ .env.example          documented configuration
```

---

*Aura is a wellbeing-support and analytics tool, not a medical device, and makes no clinical
claims. All demo data is synthetic and all ROI figures are illustrative and configurable.*
