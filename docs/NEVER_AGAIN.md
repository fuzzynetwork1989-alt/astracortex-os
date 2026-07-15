# Permanent engineering rules — AstraCortex

Mistakes that already burned us. **Do not reintroduce them.**

## 1. Never proxy LLM/API traffic through Next.js rewrites

**Symptom:** `Failed to proxy http://127.0.0.1:8000/... [Error: socket hang up] { code: 'ECONNRESET' }`

**Cause:** `next.config` rewrite `/backend/*` → FastAPI. Next’s rewrite proxy has short idle timeouts. Long calls (`/converse/reply`, Ollama model load 20–120s, even `/keys` under load) get **ECONNRESET**.

**Fix (current):**
- Browser calls **FastAPI directly**: `http://127.0.0.1:8000` (local) or Railway URL (cloud).
- FastAPI CORS: `ALLOW_CORS_ALL=true`.
- `ENABLE_LEGACY_API_PROXY=1` is the only way to re-enable rewrites — leave it off.

**Wrong (do not restore):**
```ts
// frontend getApiUrl() → `${origin}/backend`
// next.config rewrites /backend → :8000
```

**Right:**
```ts
getApiUrl() → "http://127.0.0.1:8000" // or NEXT_PUBLIC_API_URL
```

## 2. Never rely on SSE through a Next rewrite for chat

Streams buffer or hang. Use `POST /converse/reply` (full JSON) for chat reliability.

## 3. Never leave Docker API without restart policy / healthcheck

API must be `restart: unless-stopped` with `/ready` healthcheck so it comes back if killed.

## 4. Never bind-mount live Python with --reload for “prod local”

Mid-request restarts drop sockets. Compose mounts only `data/uploads`, not app source with reload.

## 5. Never use default “Nexus/70B” for casual chat UI

First load freezes the UI for minutes. Default **Seed (`qwen2.5:3b`)** for chat.

## 6. Prefer 127.0.0.1 over localhost on Windows

`localhost` can resolve to `::1` while the API listens on IPv4 only → failed fetch.

## 7. Health checks must not call Ollama every time

`/ready` = DB only. `/health` may include brain status but should cache (~15s).

## Quick recovery checklist

```powershell
# 1. Docker Desktop open
cd C:\Users\synov\.grok\downloads\astracortex
docker compose up -d --build postgres redis api

# 2. Prove API
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/health

# 3. Frontend (direct API)
cd frontend
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
npm run build
npm run start

# 4. Browser hard refresh (Ctrl+Shift+R)
# Chat should POST to http://127.0.0.1:8000/converse/reply — check Network tab
```
