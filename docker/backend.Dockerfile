# API and data pipelines (one image, different commands).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so code changes do not invalidate this layer.
COPY requirements.lock pyproject.toml README.md ./
RUN pip install -r requirements.lock

COPY alembic.ini ./
COPY backend ./backend
COPY pipelines ./pipelines
COPY database ./database
COPY data/synthetic/MANIFEST.json data/synthetic/scenarios.json ./data/synthetic/
RUN pip install --no-deps -e . \
    && useradd --create-home appuser \
    && mkdir -p data/processed \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
