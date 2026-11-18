FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/hotel.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /data \
    && chown app:app /data

COPY --chown=app:app service ./service
USER app

EXPOSE 8000
VOLUME ["/data"]

CMD ["uvicorn", "service.application:app", "--host", "0.0.0.0", "--port", "8000"]
