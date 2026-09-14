# Production image for the compliance API.
#
# Build context is the services/api directory (the monorepo convention used by
# Railway, Koyeb and docker itself):
#   docker build -t mineguard-api services/api
#
# On first boot the container runs `alembic upgrade head` before binding
# uvicorn, so a scaled-up instance never serves requests against a stale
# schema. The healthcheck path is /health.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# curl is used by the container-level healthcheck; libpq5 ships the shared
# libraries psycopg-binary links against at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, lockfile-exact dependency installation.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Layer cache: project metadata first, source last.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
# Migration config; without it `alembic upgrade head` fails at container start.
COPY alembic.ini ./alembic.ini

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

# Railway/Koyeb inject PORT; default to 8000 for local runs. exec keeps signal
# handling intact so shutdowns are clean.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
