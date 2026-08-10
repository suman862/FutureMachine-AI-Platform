FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/cache \
    TRANSFORMERS_CACHE=/models/cache

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /models/cache \
    && chown -R appuser:appuser /models

WORKDIR /app

COPY requirements-vision.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-vision.txt

COPY app.py .

USER appuser
EXPOSE 8002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
