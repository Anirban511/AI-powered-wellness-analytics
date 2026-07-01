# Validation — real-world benchmark

`scripts/seed_data.py` generates synthetic demo data for pipeline development and
reproducible dashboards. This folder answers a different question: **does the actual,
shipped sentiment + stress-scoring logic produce a sensible signal on real text with
real, human-assigned severity labels?**

It imports `analyze_sentiment()` and `stress_score()` directly from `app/nlp/sentiment.py` —
the same functions the live app calls on every journal entry. Nothing here is a duplicate or
simplified copy of that logic.

## Dataset
[**Sentiment Analysis for Mental Health**](https://www.kaggle.com/datasets/suchintikasarkar/sentiment-analysis-for-mental-health)
(Kaggle, by suchintikasarkar) — **52,681** labeled real-world statements across 7 status
categories: Normal, Depression, Suicidal, Anxiety, Bipolar, Stress, Personality Disorder.

## Run it
```bash
python validation/download_dataset.py    # fetches and caches the CSV (one-time, ~30 MB)
python validation/run_real_data_validation.py
```
Results print to console and save to `validation/results/summary_by_category.csv`.
The raw CSV and results are gitignored — re-run the two commands above to reproduce.

## What the result shows (last run)

| status                | mean stress | % flagged high-stress (≥60) | % negative sentiment |
|---|---|---|---|
| Anxiety               | 54.2 | 51.6% | 71.5% |
| Suicidal              | 53.8 | 57.0% | 73.6% |
| Depression            | 51.0 | 51.8% | 67.7% |
| Stress                | 47.5 | 43.7% | 63.3% |
| Personality disorder  | 41.9 | 39.0% | 52.1% |
| Bipolar               | 41.7 | 36.5% | 53.6% |
| **Normal**            | **30.9** | **6.7%** | 25.0% |

Processed **52,681** statements in **56.85s** (**927** statements/sec).

**The headline result:** mean stress score for Suicidal+Depression-labeled text is
**52.2**, versus **30.9** for Normal-labeled text — a **21.3-point separation**, produced
by a scoring function that never sees the label. That's external evidence the scoring
logic tracks real severity, not just an artifact of the synthetic demo data.

## Honest scope
This validates that the *signal direction* is correct (more severe labels → higher
stress scores) — it is **not** a precision/recall/accuracy benchmark, because
`stress_score()` is a continuous, unsupervised score, not a classifier making a
discrete prediction against these 7 labels. It also doesn't validate clinical
accuracy — Aura is a non-clinical wellbeing-support tool, and these are real social-media
statements, not equivalent to a clinical mood journal. Treat this as "the unsupervised
score correlates with real, human-labeled severity," which is exactly what it is.
