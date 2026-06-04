# phase4_backend — AI Booking Bot API (replaces Railway/Nixpacks build)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Container-internal fixed port (Traefik routes to this; nothing published to host)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
