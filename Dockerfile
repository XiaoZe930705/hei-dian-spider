# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Chromium for headless PDF rendering + minimal fonts for CJK.
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Taipei

RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium \
      fonts-noto-cjk \
      tzdata \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist reports and raw HTML
VOLUME ["/app/data"]

CMD ["python", "spider.py"]
