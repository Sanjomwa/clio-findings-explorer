FROM python:3.12-slim

# Built from the repository root (docker build -f backend/Dockerfile .) so the image carries
# the curated content and the snapshot and runs without volumes. One image serves the API
# and the seed job.
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    CONTENT_DIR=/content \
    SNAPSHOT_DIR=/data/snapshot

RUN pip install --no-cache-dir uv==0.11.25 \
    && useradd --create-home --uid 10001 app

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY content /content
COPY data/snapshot /data/snapshot

USER app
EXPOSE 8000
# --no-access-log: uvicorn's access line prints the client IP; the app writes its own (app/telemetry.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
