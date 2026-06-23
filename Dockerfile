FROM python:3.12-slim

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY agent/ agent/
COPY api/ api/
COPY static/ static/
COPY prompts/ prompts/
COPY etl/__init__.py etl/config.py etl/metric_windows.py etl/

ENV ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
