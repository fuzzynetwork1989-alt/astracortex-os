from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import (
    auth,
    billing,
    chat,
    converse,
    documents,
    feedback,
    keys,
    memory,
    metrics,
    search,
    sessions,
    settings,
    tasks,
    traces,
    v1_openai,
    workflows,
    xr,
)
from app.core.config import get_settings
from app.core.logging import logger
from app.db.models import Base
from app.db.session import engine
from app.services import brain


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    st = await brain.brain_status()
    logger.info(
        "AstraCortex OS v2 online — ollama=%s cloud=%s models=%s",
        st.get("ollama_online"),
        st.get("cloud_configured"),
        len(st.get("ollama_models") or []),
    )
    yield
    await engine.dispose()


app = FastAPI(
    title="AstraCortex OS",
    description="Hybrid Cognitive Operating System — local Ollama + cloud + sellable OpenAI-compatible API",
    version="2.1.2",
    lifespan=lifespan,
)

cfg = get_settings()
# Always include both localhost and 127.0.0.1 — browsers treat them as different origins
_origins = list(
    dict.fromkeys(
        cfg.cors_origin_list
        + [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://127.0.0.1:3001",
            "http://localhost:3001",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:19006",
            "http://127.0.0.1:19006",
        ]
    )
)
# Dev default: open CORS so browser→API never looks like a "CORS" failure when the real bug is a 500
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cfg.allow_cors_all else _origins,
    allow_credentials=not cfg.allow_cors_all,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc):  # noqa: ANN001
    """Ensure JSON 500s always leave the app (CORS middleware still adds headers)."""
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # Framework handlers normally win; if we still get these, respond correctly (never re-raise).
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {exc.__class__.__name__}: {exc}"},
    )

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(converse.router, prefix="/converse", tags=["converse"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(memory.router, prefix="/memory", tags=["memory"])
app.include_router(traces.router, prefix="/traces", tags=["traces"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(keys.router, prefix="/keys", tags=["keys"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(xr.router, prefix="/xr", tags=["xr"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(v1_openai.router, prefix="/v1", tags=["openai-compatible"])


# Lightweight health cache — never block every probe on Ollama tags
_health_cache: dict = {"ts": 0.0, "payload": None}


@app.get("/health")
async def health():
    import time as _time

    from app.services import qlora
    from app.services.working_memory import get_redis

    now = _time.time()
    if _health_cache["payload"] and now - float(_health_cache["ts"]) < 15:
        return _health_cache["payload"]

    st = await brain.brain_status()
    redis_client = await get_redis()
    payload = {
        "status": "ok",
        "product": "AstraCortex OS",
        "version": "2.1.2",
        "hybrid": {
            "mode": get_settings().inference_mode,
            "local_ollama": st.get("ollama_online"),
            "cloud_xai": st.get("cloud_configured"),
            "redis": redis_client is not None,
        },
        "llm_configured": bool(st.get("cloud_configured") or st.get("ollama_online")),
        "brain": st,
        "qlora_adapters": qlora.list_adapters(),
        "public_api_url": get_settings().public_api_url,
        "client_hint": "Browser must call this API directly (not via Next /backend proxy)",
    }
    _health_cache["ts"] = now
    _health_cache["payload"] = payload
    return payload


@app.get("/ready")
async def ready():
    """Liveness for Docker/Railway — DB only, never Ollama (keeps healthchecks fast)."""
    from fastapi.responses import JSONResponse

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ready": False, "error": str(exc)}, status_code=503)
