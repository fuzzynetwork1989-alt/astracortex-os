# AstraCortex OS

**Next-gen hybrid Cognitive Operating System** — plan, retrieve, act, reflect, remember.

| Layer | Stack |
|---|---|
| Web | Next.js (Vercel) |
| API | FastAPI (Railway) |
| Local brain | Ollama (`deepseek-r1`, `llama3.1`, `qwen2.5`) |
| Cloud brain | Optional xAI Grok |
| Data | PostgreSQL + pgvector, Redis (optional) |
| API product | OpenAI-compatible `/v1` + sellable `sk-astra-` tokens |
| Clients | Web · Electron desktop · Expo mobile · WebXR |

## Quick start (local)

```bash
cp .env.example .env
docker compose up -d postgres redis api
cd frontend && npm install && npm run dev
```

- UI: http://localhost:3000  
- API: http://localhost:8000/docs  

## Tests

```bash
cd backend && pip install -r requirements.txt && pytest -q
cd frontend && npm ci && npm run build
```

## Cloud deploy (automated)

See [DEPLOY.md](./DEPLOY.md):

1. Push to GitHub `fuzzynetwork1989-alt/astracortex-os`
2. **Railway** → root `backend/` + Postgres
3. **Vercel** → root `frontend/` + `NEXT_PUBLIC_API_URL`

CI: `.github/workflows/ci.yml` (pytest + next build + docker).

## Hybrid modes

- `INFERENCE_MODE=local` — Ollama only  
- `INFERENCE_MODE=cloud` — xAI only  
- `INFERENCE_MODE=hybrid` — local first, cloud for sovereign when key present  

## Product surfaces

Chat · Goals/OS loop · Knowledge RAG · Memory · Workflows · Traces · API Keys · Billing · Settings · XR  

## License

Proprietary — AstraCortex / fuzzynetwork1989-alt  
