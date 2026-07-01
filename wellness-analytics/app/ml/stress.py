"""
Stress trend detection (ML / time-series).

Given a user's daily stress series, we surface the signals a wellbeing product
actually needs:

  - EWMA smoothing          -> a stable "current state" that ignores single bad days
  - linear-regression slope -> is stress rising, falling, or stable? (sklearn)
  - volatility              -> how erratic is the week (std of daily scores)
  - z-score anomalies       -> stand-out spike days worth flagging
  - 7-day forecast          -> projected next-week average (slope extrapolation)

Everything degrades gracefully with sparse data (a brand-new user with 2 entries
should not crash the dashboard), which is the realistic production constraint.
"""
import datetime as dt

import numpy as np
from sklearn.linear_model import LinearRegression


def _daily_series(entries: list[dict]) -> tuple[list[dt.date], np.ndarray, np.ndarray]:
    """
    Collapse entries to one stress value per day (mean), sorted by date.
    entries: [{"date": date, "stress": float, "sentiment": float}, ...]
    """
    by_day: dict[dt.date, list[tuple[float, float]]] = {}
    for e in entries:
        by_day.setdefault(e["date"], []).append((e["stress"], e["sentiment"]))
    days = sorted(by_day)
    stress = np.array([np.mean([s for s, _ in by_day[d]]) for d in days], dtype=float)
    sentiment = np.array([np.mean([c for _, c in by_day[d]]) for d in days], dtype=float)
    return days, stress, sentiment


def _ewma(values: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    out = np.zeros_like(values, dtype=float)
    if len(values) == 0:
        return out
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _state(level: float) -> str:
    if level < 30:
        return "low"
    if level < 50:
        return "moderate"
    if level < 70:
        return "elevated"
    return "high"


def analyze_trend(entries: list[dict]) -> dict:
    """Main entry point — returns a JSON-serialisable trend report."""
    if not entries:
        return {
            "series": [], "state": "low", "trend": "stable", "slope_per_day": 0.0,
            "volatility": 0.0, "forecast_next_week": 0.0, "anomalies": [],
            "summary": "No entries yet. Start journaling to see your trends.",
        }

    days, stress, sentiment = _daily_series(entries)
    ewma = _ewma(stress)
    current_level = float(ewma[-1])

    # --- Trend via linear regression on the last 14 available days ---
    window = min(len(stress), 14)
    y = stress[-window:]
    x = np.arange(window).reshape(-1, 1)
    if window >= 2:
        reg = LinearRegression().fit(x, y)
        slope = float(reg.coef_[0])             # stress points per day
        forecast = float(reg.predict([[window + 6]])[0])  # ~1 week ahead
    else:
        slope, forecast = 0.0, current_level
    forecast = max(0.0, min(100.0, forecast))

    if slope > 1.0:
        trend = "rising"
    elif slope < -1.0:
        trend = "falling"
    else:
        trend = "stable"

    volatility = float(np.std(stress)) if len(stress) > 1 else 0.0

    # --- Anomaly detection: z-score spikes above the personal baseline ---
    anomalies = []
    if len(stress) >= 4:
        mu, sd = float(np.mean(stress)), float(np.std(stress))
        if sd > 0:
            for d, val in zip(days, stress):
                z = (val - mu) / sd
                if z >= 1.8:  # clearly above this person's normal
                    anomalies.append({"date": d.isoformat(), "stress": round(val, 1),
                                      "z": round(z, 2)})

    series = [
        {"date": d.isoformat(), "stress": round(float(s), 1),
         "sentiment": round(float(c), 3), "ewma": round(float(w), 1)}
        for d, s, c, w in zip(days, stress, sentiment, ewma)
    ]

    state = _state(current_level)
    summary = _summarise(state, trend, slope, current_level, forecast, len(anomalies))

    return {
        "series": series,
        "state": state,
        "trend": trend,
        "slope_per_day": round(slope, 2),
        "volatility": round(volatility, 1),
        "forecast_next_week": round(forecast, 1),
        "anomalies": anomalies,
        "summary": summary,
    }


def _summarise(state, trend, slope, level, forecast, n_anom) -> str:
    parts = [f"Current stress is {state} (~{round(level)}/100)."]
    if trend == "rising":
        parts.append(f"It's trending up (+{slope:.1f}/day); projected ~{round(forecast)} next week.")
    elif trend == "falling":
        parts.append(f"It's easing ({slope:.1f}/day); projected ~{round(forecast)} next week.")
    else:
        parts.append("It's been broadly stable.")
    if n_anom:
        parts.append(f"{n_anom} spike day(s) stood out above your baseline.")
    return " ".join(parts)
