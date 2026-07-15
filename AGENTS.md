# Agent notes for AstraCortex

Read `docs/NEVER_AGAIN.md` before changing networking.

## Critical

- **Do not** add Next.js rewrites that proxy `/backend` → FastAPI for app traffic.
- Browser → **direct** API (`http://127.0.0.1:8000` or `NEXT_PUBLIC_API_URL`).
- Chat uses `POST /converse/reply` (not SSE through a proxy).
- Default chat tier: **seed**.
- API Docker: no code bind-mount + reload; use `restart: unless-stopped`.
