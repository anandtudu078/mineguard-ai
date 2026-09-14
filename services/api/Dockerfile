# Production image for the compliance API.
#
# Build from the repository root so the lockfile context is available:
#   docker build -f services/api/Dockerfile -t mineguard-api .
#
# On Koyeb, set the Docker build context to the repository root and this file
# as the Dockerfile. The healthcheck path is /health.

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
COPY services/api/pyproject.toml services/api/uv.lock ./services/api/
RUN cd services/api && uv sync --frozen --no-dev

COPY services/api/app ./services/api/app
COPY services/api/alembic ./services/api/alembic
# Migration config; without it `alembic upgrade head` fails at container start.
COPY services/api/alembic.ini ./services/api/alembic.ini

WORKDIR /app/services/api

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

# Migrations run before the server binds so a scaled-up instance never serves
# requests against a stale schema. exec keeps signal handling intact.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
