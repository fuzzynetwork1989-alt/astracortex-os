# AstraCortex — Cloud deployment (Railway + Vercel)

**Cloud-first:** browser → Vercel (Next.js) → Railway (FastAPI) → xAI (LLM).  
No local Ollama required on the server.

## Architecture

```
User browser / desktop / mobile
        │
        ▼
  Vercel (frontend)     NEXT_PUBLIC_API_URL=https://api....railway.app
        │  CORS direct fetch (never Next proxy)
        ▼
  Railway (FastAPI)     Postgres + Redis plugins
        │
        ▼
  xAI Grok API          XAI_API_KEY (required for cloud LLM)
```

Repo: `https://github.com/fuzzynetwork1989-alt/astracortex-os`

---

## 1. Push latest code

```bash
git push origin main
```

---

## 2. Railway (API + Postgres + Redis)

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Select `fuzzynetwork1989-alt/astracortex-os`
3. **Root Directory:** `backend`
4. **Builder:** Dockerfile (auto from `backend/Dockerfile`)
5. Add plugins:
   - **PostgreSQL** (Railway sets `DATABASE_URL` — app auto-converts to `asyncpg` + SSL)
   - **Redis** (optional; in-memory WM if missing)
6. **Variables** (service settings):

| Variable | Value |
|----------|--------|
| `JWT_SECRET` | long random string |
| `INFERENCE_MODE` | `cloud` |
| `XAI_API_KEY` | your xAI key (`xai-...`) |
| `XAI_BASE_URL` | `https://api.x.ai/v1` |
| `ALLOW_CORS_ALL` | `true` |
| `UPLOAD_DIR` | `/tmp/uploads` |
| `PUBLIC_API_URL` | `https://<your-railway-domain>` (set after first deploy) |
| `DEFAULT_TOKEN_BALANCE` | `1000000` |
| `HUMAN_LIKE_SYSTEM` | `true` |
| `PRODUCT_TIER_DEFAULT` | `seed` |

7. Health check path: `/ready` (or `/health`)
8. Generate domain → copy URL → set `PUBLIC_API_URL` to that HTTPS URL
9. Redeploy

### Verify API

```bash
curl https://YOUR-APP.up.railway.app/health
curl https://YOUR-APP.up.railway.app/ready
```

---

## 3. Vercel (frontend)

1. [vercel.com](https://vercel.com) → **Add New** → **Project** → import the same GitHub repo
2. **Root Directory:** `frontend`
3. Framework: Next.js
4. Environment variable:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | `https://YOUR-APP.up.railway.app` (no trailing slash) |

5. Deploy → open the Vercel URL → **Register** → Chat / API keys

---

## 4. Optional: hybrid (cloud API + your home Ollama)

Only if you expose Ollama safely (tunnel):

```env
INFERENCE_MODE=hybrid
OLLAMA_BASE_URL=https://your-tunnel.example
XAI_API_KEY=...   # failover
```

Default cloud path needs **only** `XAI_API_KEY`.

---

## 5. Sellable OpenAI-compatible API

After register, use the `sk-astra-...` key:

```bash
curl https://YOUR-APP.up.railway.app/v1/chat/completions \
  -H "Authorization: Bearer sk-astra-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"seed","messages":[{"role":"user","content":"hello"}]}'
```

---

## 6. Desktop / mobile clients

- Electron: set API URL to Railway domain (or keep Vercel UI URL for shell)
- Expo: `EXPO_PUBLIC_API_URL=https://YOUR-APP.up.railway.app`

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Register “Failed to fetch” | `NEXT_PUBLIC_API_URL` wrong or CORS; set `ALLOW_CORS_ALL=true` |
| 500 on /ready | Postgres not linked / `DATABASE_URL` missing |
| Chat empty / offline | Set `XAI_API_KEY` + `INFERENCE_MODE=cloud` |
| Socket hang up via Next | Never proxy LLM through Next rewrites |
