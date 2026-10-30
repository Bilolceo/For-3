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

# Ma'lumotlar bazasi /app/data da — uni volume qilib ulang (Railway: Volume → /app/data;
# docker-compose: ./data:/app/data). Railway Dockerfile'dagi VOLUME buyrug'ini qabul qilmaydi,
# volume'lar root egaligida mount bo'lgani uchun non-root user ham ishlatilmaydi.
RUN mkdir -p /app/data

CMD ["python", "-m", "lovebot"]
