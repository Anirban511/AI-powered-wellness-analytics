"""
Aura — external validation against a real, public, labeled dataset.

Why this exists
----------------
The demo/seed data shipped with Aura (scripts/seed_data.py) is synthetic, by
design, for pipeline development and reproducible demos. This script answers a
different and important question: does the actual sentiment + stress-scoring
logic in app/nlp/sentiment.py produce a sensible signal on REAL text, where
the ground-truth severity label was assigned by real people?

It imports analyze_sentiment() and stress_score() directly from the live
package — this is NOT a re-implementation or a copy of the logic, so the
numbers below are a true benchmark of the shipped code, not of some sibling
script that happens to look similar.

Dataset
-------
"Sentiment Analysis for Mental Health" (Kaggle, created by suchintikasarkar),
52,681 labeled real-world statements across 7 status categories (Normal,
Depression, Suicidal, Anxiety, Bipolar, Stress, Personality Disorder).
Source: https://www.kaggle.com/datasets/suchintikasarkar/sentiment-analysis-for-mental-health
Mirror used by this script: a public GitHub mirror of the same CSV (see
download_dataset.py in this folder).

What this validates
--------------------
The stress_score() function never sees the status label — it only sees raw
text. If real "Suicidal"/"Depression"-labeled statements score reliably
higher than real "Normal"-labeled statements, that is genuine external
evidence the unsupervised scoring logic tracks real severity, not just an
assumption baked into the demo data.

Run
---
    python validation/download_dataset.py     # fetches the CSV once (cached)
    python validation/run_real_data_validation.py

Outputs a console report and validation/results/summary_by_category.csv.
"""
import os
import sys
import time

import pandas as pd

# Make the real app package importable when run as `python validation/run_real_data_validation.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.nlp.sentiment import analyze_sentiment, stress_score  # noqa: E402  (the REAL, shipped logic)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATA_PATH = os.path.join(DATA_DIR, "mental_health_data.csv")


def load_dataset() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}.\n"
            "Run `python validation/download_dataset.py` first to fetch it."
        )
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["statement"]).reset_index(drop=True)
    df["statement"] = df["statement"].astype(str)
    return df


def run_pipeline(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Run the REAL analyze_sentiment() + stress_score() over every statement."""
    t0 = time.time()
    sentiments = df["statement"].apply(analyze_sentiment)
    df["compound"] = sentiments.apply(lambda s: s["compound"])
    df["label"] = sentiments.apply(lambda s: s["label"])
    df["stress_score"] = [
        stress_score(text, s) for text, s in zip(df["statement"], sentiments)
    ]
    elapsed = time.time() - t0
    return df, elapsed


def report(df: pd.DataFrame, elapsed: float) -> pd.DataFrame:
    n = len(df)
    print(f"Loaded {n} real, labeled statements across {df['status'].nunique()} status categories")

    print("\n=== RUNTIME (real app.nlp.sentiment functions) ===")
    print(f"Processed {n} statements in {elapsed:.2f}s  ({n/elapsed:.0f} statements/sec)")

    print("\n=== SENTIMENT LABEL DISTRIBUTION (real output) ===")
    counts = df["label"].value_counts()
    pcts = (df["label"].value_counts(normalize=True) * 100).round(1)
    for lbl in counts.index:
        print(f"  {lbl:10s} {counts[lbl]:>6d}  ({pcts[lbl]}%)")

    print("\n=== STRESS SCORE BY REAL LABELED STATUS ===")
    summary = (
        df.groupby("status")["stress_score"]
        .agg(mean_stress="mean", std_stress="std", n="count")
        .round(1)
    )
    summary["pct_high_stress_ge60"] = df.groupby("status")["stress_score"].apply(
        lambda s: round((s >= 60).mean() * 100, 1)
    )
    summary["pct_negative_sentiment"] = df.groupby("status")["label"].apply(
        lambda s: round((s == "negative").mean() * 100, 1)
    )
    summary = summary.sort_values("mean_stress", ascending=False)
    print(summary.to_string())

    print("\n=== VALIDATION: high-risk vs. normal separation ===")
    high_risk = df[df["status"].isin(["Suicidal", "Depression"])]["stress_score"].mean()
    normal = df[df["status"] == "Normal"]["stress_score"].mean()
    print(f"Mean stress score, Suicidal+Depression (real labels): {high_risk:.1f}")
    print(f"Mean stress score, Normal (real labels):               {normal:.1f}")
    print(f"Separation:                                            {high_risk - normal:.1f} points")

    return summary


def main():
    df = load_dataset()
    df, elapsed = run_pipeline(df)
    summary = report(df, elapsed)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary_by_category.csv"))
    print(f"\nSaved summary to {RESULTS_DIR}/summary_by_category.csv")


if __name__ == "__main__":
    main()
