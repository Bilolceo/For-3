FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lovebot ./lovebot
COPY content ./content

RUN useradd --create-home lovebot && mkdir -p /app/data && chown -R lovebot:lovebot /app
USER lovebot

VOLUME ["/app/data"]
CMD ["python", "-m", "lovebot"]
