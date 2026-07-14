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
    version="2.0.0",
    lifespan=lifespan,
)

cfg = get_settings()
_origins = cfg.cors_origin_list + [
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://localhost:8081",
    "http://localhost:19006",
]
if cfg.allow_cors_all:
    # Vercel preview URLs + hybrid clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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


@app.get("/health")
async def health():
    st = await brain.brain_status()
    from app.services import qlora
    from app.services.working_memory import get_redis

    redis_client = await get_redis()
    return {
        "status": "ok",
        "product": "AstraCortex OS",
        "version": "2.1.0",
        "hybrid": {
            "mode": get_settings().inference_mode,
            "local_ollama": st.get("ollama_online"),
            "cloud_xai": st.get("cloud_configured"),
            "redis": redis_client is not None,
        },
        "llm_configured": st.get("cloud_configured") or st.get("ollama_online"),
        "brain": st,
        "qlora_adapters": qlora.list_adapters(),
        "public_api_url": get_settings().public_api_url,
    }


@app.get("/ready")
async def ready():
    """Railway / load balancer readiness — DB must respond."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as exc:  # noqa: BLE001
        return {"ready": False, "error": str(exc)}
