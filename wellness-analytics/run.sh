#!/usr/bin/env bash
# ── Aura: local one-command run (no Docker) ──────────────────────────────────
# Uses SQLite by default — zero database setup. Creates a virtualenv, installs
# dependencies, then launches the app (which auto-creates tables + seeds demo
# data on first run). Open http://localhost:8000 when it's up.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[run] Creating virtual environment…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[run] Installing dependencies…"
pip install -q -r requirements.txt

echo "[run] Launching Aura on http://localhost:8000  (Ctrl+C to stop)"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
