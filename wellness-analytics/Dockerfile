# ── Aura: application image ──────────────────────────────────────────────────
FROM python:3.12-slim

# Keep Python lean and logs unbuffered (so container logs stream live)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for psycopg2, plus a Postgres client used by the
# entrypoint's wait-for-db check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application
COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
