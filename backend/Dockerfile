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
EXPOSE 8000

# Long keep-alive for Ollama/LLM requests (minutes, not seconds)
# Do NOT use --reload in production/docker (causes mid-request restarts)
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/ready" || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-keep-alive 300 --proxy-headers --forwarded-allow-ips="*"
