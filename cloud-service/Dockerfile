FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAAR_DB_PATH=/data/results.db

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --system --uid 10001 caar && mkdir -p /data && chown caar /data
USER caar

EXPOSE 8000
# Một worker: cache nonce chống replay nằm trong bộ nhớ của tiến trình (security.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
