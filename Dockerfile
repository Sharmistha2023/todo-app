# Todo List app — DKubeX platform app image.
# Runtime only; the Dockerfile builds the chart's Deployment directly.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY static/ ./static/

# The chart runs the pod as a non-root user; match that here.
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

# PORT is injected by the chart; DKUBEX_BASE_PATH is used by main.py to mount routes.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port \"${PORT}\""]
