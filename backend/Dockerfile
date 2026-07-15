FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
# Hybrid defaults: local Ollama when reachable, xAI failover when XAI_API_KEY set
ENV UPLOAD_DIR=/tmp/uploads
ENV ALLOW_CORS_ALL=true
ENV INFERENCE_MODE=hybrid
EXPOSE 8000

# Railway uses $PORT; keep-alive high for LLM
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/ready" || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 300 --proxy-headers --forwarded-allow-ips="*"
