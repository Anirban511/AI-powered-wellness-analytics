"""
Optional test: confirms the real-data validation pipeline runs correctly and that
the stress-scoring logic actually separates real labeled severity categories.

Skipped automatically if the dataset hasn't been downloaded (see validation/README.md),
so the main `pytest -q` suite stays fast and offline. To include this test:

    python validation/download_dataset.py
    pytest validation/ -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.run_real_data_validation import DATA_PATH, load_dataset, run_pipeline  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.path.exists(DATA_PATH),
    reason="Real dataset not downloaded — run `python validation/download_dataset.py` first",
)


def test_real_pipeline_runs_and_produces_scores():
    df = load_dataset()
    # Use a sample for test speed — full run is exercised via run_real_data_validation.py
    sample = df.sample(n=min(500, len(df)), random_state=7).reset_index(drop=True)
    sample, elapsed = run_pipeline(sample)
    assert (sample["stress_score"].between(0, 100)).all()
    assert elapsed > 0


def test_high_risk_separates_from_normal():
    df = load_dataset()
    sample = df.sample(n=min(3000, len(df)), random_state=7).reset_index(drop=True)
    sample, _ = run_pipeline(sample)
    high_risk = sample[sample["status"].isin(["Suicidal", "Depression"])]["stress_score"].mean()
    normal = sample[sample["status"] == "Normal"]["stress_score"].mean()
    # Real, human-labeled high-risk text should score meaningfully higher than "Normal".
    assert high_risk > normal + 10
