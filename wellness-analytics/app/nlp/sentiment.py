"""
Sentiment analysis (NLP).

Pluggable backend so we can trade cost for accuracy without touching callers:
  - "vader": fast lexicon model, deterministic, no downloads (default / Docker).
  - "transformer": distilbert SST-2 via HuggingFace (heavier, lazy-loaded).

We also derive a 0..100 *stress score* from the sentiment signal plus a small
stressor lexicon. Stress is not the same as negativity — "exhausted by deadlines"
and "sad about the news" are both negative but the first is more stress-laden — so
explicit stressor terms nudge the score upward.
"""
from functools import lru_cache

from app.config import settings

# Words that signal *stress* specifically (load, pressure, depletion), used to
# amplify the stress score beyond raw negativity.
STRESSOR_TERMS = {
    "deadline", "deadlines", "exam", "exams", "overwhelmed", "overwhelming",
    "pressure", "burnout", "burnt", "exhausted", "exhausting", "anxious",
    "anxiety", "panic", "workload", "overload", "behind", "swamped", "tired",
    "sleepless", "insomnia", "cant sleep", "no sleep", "money", "rent", "bills",
    "fight", "argument", "conflict", "fired", "rejection", "rejected", "deadline",
}


@lru_cache(maxsize=1)
def _vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()


@lru_cache(maxsize=1)
def _transformer():
    # Imported lazily so the default install never needs torch/transformers.
    from transformers import pipeline
    return pipeline("sentiment-analysis", model=settings.TRANSFORMER_MODEL)


def _label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def analyze_sentiment(text: str) -> dict:
    """Return {compound, label, pos, neu, neg} in a backend-agnostic shape."""
    if settings.SENTIMENT_BACKEND == "transformer":
        try:
            res = _transformer()(text[:512])[0]
            # Map POSITIVE/NEGATIVE prob to a [-1, 1] compound for a unified schema.
            signed = res["score"] if res["label"] == "POSITIVE" else -res["score"]
            return {
                "compound": round(signed, 4),
                "label": _label(signed),
                "pos": round(max(signed, 0.0), 4),
                "neg": round(max(-signed, 0.0), 4),
                "neu": round(1 - abs(signed), 4),
            }
        except Exception:
            pass  # fall back to VADER if model/internet unavailable

    s = _vader().polarity_scores(text)
    return {
        "compound": round(s["compound"], 4),
        "label": _label(s["compound"]),
        "pos": round(s["pos"], 4),
        "neu": round(s["neu"], 4),
        "neg": round(s["neg"], 4),
    }


def stress_score(text: str, sentiment: dict) -> float:
    """
    Composite stress score in [0, 100].

    base       : how negative the overall sentiment is (compound -> [0,1])
    intensity  : the negative fraction of the text (sharp negativity reads as load)
    stressors  : explicit stressor keywords amplify the score
    """
    compound = sentiment["compound"]
    base = (1.0 - compound) / 2.0                  # 0 (very +) .. 1 (very -)
    intensity = sentiment["neg"]                   # 0..1
    low = text.lower()
    hits = sum(1 for term in STRESSOR_TERMS if term in low)
    stressor_boost = min(hits, 4) * 0.06           # up to +0.24

    raw = 0.62 * base + 0.30 * intensity + stressor_boost
    return round(max(0.0, min(1.0, raw)) * 100, 1)
