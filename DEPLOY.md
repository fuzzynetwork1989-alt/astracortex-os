# AstraCortex — Hybrid deployment

**Hybrid Cognitive OS:** local Ollama **and** cloud xAI, with Railway API + Vercel UI.

```
                    ┌─────────────────┐
  Browser / desktop │  Vercel (UI)    │  NEXT_PUBLIC_API_URL → Railway
                    └────────┬────────┘
                             │ direct CORS fetch (never Next proxy)
                    ┌────────▼────────┐
                    │ Railway FastAPI │  Postgres + Redis
                    └────────┬────────┘
                 ┌───────────┴───────────┐
                 ▼                       ▼
        Ollama (local/tunnel)      xAI Grok (cloud)
        seed/nexus first           failover + sovereign
```

| Mode | When |
|------|------|
| **hybrid** (default) | Ollama first; if down or fails → xAI if `XAI_API_KEY` set |
| local | Ollama only (fully offline) |
| cloud | xAI only (no Ollama) |

Repo: `https://github.com/fuzzynetwork1989-alt/astracortex-os`

---

## A. Local hybrid (this machine)

```bash
# 1) Ollama on host
ollama serve
ollama pull qwen2.5:3b

# 2) Optional cloud failover
# set XAI_API_KEY in .env

# 3) Stack
docker compose up -d postgres redis api
cd frontend && set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 && npm run dev
```

`.env` / `docker-compose` already use `INFERENCE_MODE=hybrid` and  
`OLLAMA_BASE_URL=http://host.docker.internal:11434`.

Verify:

```bash
curl http://127.0.0.1:8000/health
# hybrid.local_ollama should be true; set XAI_API_KEY for cloud_xai true
```

---

## B. Cloud hybrid (Railway + Vercel)

### 1. Railway API

1. Deploy GitHub repo → root **`backend`**
2. Plugins: **PostgreSQL** + **Redis**
3. Variables (see `backend/.env.cloud.example`):

| Variable | Hybrid value |
|----------|----------------|
| `INFERENCE_MODE` | **`hybrid`** |
| `XAI_API_KEY` | required for cloud half |
| `OLLAMA_BASE_URL` | empty **or** your Ollama tunnel URL |
| `ALLOW_CORS_ALL` | `true` |
| `JWT_SECRET` | long random |
| `UPLOAD_DIR` | `/tmp/uploads` |
| `PUBLIC_API_URL` | `https://<railway-domain>` |

4. Domain → health `/ready` or `/health`

**Without Ollama tunnel:** hybrid still works — Ollama attempts fail fast, then **xAI** answers.  
**With tunnel:** seed/nexus hit your home GPU/CPU first.

### 2. Vercel UI

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | `https://<railway-domain>` |

Root directory: **`frontend`**

### 3. Optional Ollama tunnel (true hybrid from cloud API)

```bash
# example: cloudflare tunnel or ngrok to host:11434
# then on Railway:
OLLAMA_BASE_URL=https://ollama.your-tunnel.example
```

---

## Routing rules (brain)

| Tier | Hybrid primary | Failover |
|------|----------------|----------|
| **Seed** | Ollama `qwen2.5:3b` | xAI executor/planner |
| **Nexus** | Ollama 8B class | xAI |
| **Sovereign** | xAI if key set | Ollama local |

---

## Clients

- Web: Vercel URL  
- Desktop Electron: same Vercel URL or set API to Railway  
- Mobile Expo: `EXPO_PUBLIC_API_URL=https://railway...`  
- Sellable API: `https://railway.../v1/chat/completions` + `sk-astra-...`

---

## Quick checks

```bash
curl https://API/health
# "inference_mode":"hybrid","local_ollama":bool,"cloud_xai":bool

curl https://API/v1/chat/completions \
  -H "Authorization: Bearer sk-astra-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"seed","messages":[{"role":"user","content":"hi"}]}'
```

Response includes `provider`: `ollama` or `xai` so you can see which half answered.
