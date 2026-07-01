#!/usr/bin/env bash
# ── Aura entrypoint ──────────────────────────────────────────────────────────
# 1. If a Postgres DATABASE_URL is configured, wait until the DB accepts
#    connections (compose starts both containers at once).
# 2. Launch the API. The app creates tables and seeds reproducible demo data
#    on startup automatically (see app/main.py), so there is nothing else to do.
set -e

if [[ "${DATABASE_URL:-}" == postgres* ]]; then
  echo "[entrypoint] Postgres backend detected — waiting for database…"
  # Parse host:port out of the URL (postgresql://user:pass@HOST:PORT/db)
  HOSTPORT=$(echo "$DATABASE_URL" | sed -E 's|.*@([^/]+)/.*|\1|')
  DB_HOST=$(echo "$HOSTPORT" | cut -d: -f1)
  DB_PORT=$(echo "$HOSTPORT" | cut -d: -f2)
  DB_PORT=${DB_PORT:-5432}

  for i in $(seq 1 30); do
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
      echo "[entrypoint] Database is ready."
      break
    fi
    echo "[entrypoint] …waiting ($i/30)"
    sleep 1
  done
fi

echo "[entrypoint] Starting Aura on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
