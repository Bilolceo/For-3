FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/app/data/lovebot.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lovebot ./lovebot
COPY content ./content

# Railway/Render volume'lari root egaligida mount bo'ladi — shuning uchun non-root user ishlatilmaydi.
# Ma'lumotlar bazasi shu papkada; uni volume qilib ulang (Railway: Volume → /app/data).
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "-m", "lovebot"]
