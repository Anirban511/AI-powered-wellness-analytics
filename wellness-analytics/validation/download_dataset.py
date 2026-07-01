"""
Downloads the real, public validation dataset used by run_real_data_validation.py.

Dataset: "Sentiment Analysis for Mental Health" (Kaggle, suchintikasarkar),
mirrored as a CSV on GitHub. 52,681 labeled real-world statements across
7 mental-health status categories. Cached locally after the first run so
validation doesn't require network access on every run.
"""
import os
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_PATH = os.path.join(DATA_DIR, "mental_health_data.csv")
SOURCE_URL = (
    "https://raw.githubusercontent.com/emirgocen03/"
    "mental-health-text-classification/main/data.csv"
)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DATA_PATH):
        print(f"Already downloaded: {DATA_PATH}")
        return
    print(f"Downloading dataset from {SOURCE_URL} ...")
    urllib.request.urlretrieve(SOURCE_URL, DATA_PATH)
    size_mb = os.path.getsize(DATA_PATH) / (1024 * 1024)
    print(f"Saved {size_mb:.1f} MB to {DATA_PATH}")


if __name__ == "__main__":
    main()
