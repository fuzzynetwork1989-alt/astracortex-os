# AstraCortex — Automated Cloud Deployment

Hybrid Cognitive OS: **local Ollama** + **cloud (Railway API + Vercel UI)** + optional **xAI**.

## 1. GitHub

Repository: `fuzzynetwork1989-alt/astracortex-os`

CI runs on every push (`backend` pytest + `frontend` next build + Docker image).

## 2. Railway (backend)

1. New project → **Deploy from GitHub** → select this repo.
2. **Root directory:** `backend`
3. Add plugins:
   - **PostgreSQL** → maps to `DATABASE_URL` (convert to `postgresql+asyncpg://...` if needed)
   - **Redis** (optional) → `REDIS_URL` (falls back to in-memory if missing)
4. Variables:

```env
JWT_SECRET=<long-random>
INFERENCE_MODE=hybrid
OLLAMA_BASE_URL=https://your-public-ollama-or-leave-empty
XAI_API_KEY=<optional-cloud-brain>
PUBLIC_API_URL=https://<your-railway-domain>
ALLOW_CORS_ALL=true
UPLOAD_DIR=/tmp/uploads
DEFAULT_TOKEN_BALANCE=1000000
HUMAN_LIKE_SYSTEM=true
```

5. Health check path: `/health`  
6. Start command is Dockerfile `CMD` (uvicorn on `$PORT`).

### DATABASE_URL note

If Railway injects `postgres://`, set:

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
```

(script `scripts/normalize_database_url.py` can help).

## 3. Vercel (frontend)

1. Import GitHub repo in Vercel.
2. **Root Directory:** `frontend`
3. Framework: Next.js
4. Env:

```env
NEXT_PUBLIC_API_URL=https://<your-railway-domain>
```

5. Deploy. Preview + production both work (CORS open when `ALLOW_CORS_ALL=true`).

## 4. Hybrid modes

| Mode | Config |
|---|---|
| Local full stack | `docker compose up` + Ollama on host |
| Cloud UI + Cloud API + local Ollama tunnel | Railway API + `OLLAMA_BASE_URL` via tunnel |
| Cloud UI + Cloud API + xAI only | `INFERENCE_MODE=cloud` + `XAI_API_KEY` |
| Hybrid | `INFERENCE_MODE=hybrid` (default) |

## 5. First-time verify

```bash
curl https://<railway>/health
curl https://<vercel>/login
# Register in UI → create API key → 
curl https://<railway>/v1/chat/completions \
  -H "Authorization: Bearer sk-astra-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"astracortex-seed","messages":[{"role":"user","content":"hi"}]}'
```

## 6. App clients

- **Desktop:** `desktop/` Electron → points at Vercel URL  
- **Mobile:** `mobile/` Expo → `EXPO_PUBLIC_API_URL=https://<railway>`  
- **XR:** Web `/xr` against same API  
