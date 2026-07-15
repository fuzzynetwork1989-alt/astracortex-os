from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def _normalize_db_url(url: str) -> str:
    """Railway/Heroku inject postgres:// — convert to asyncpg + SSL for cloud hosts."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    cloud_host = any(
        x in host
        for x in (
            "railway",
            "rlwy.net",
            "render.com",
            "amazonaws.com",
            "neon.tech",
            "supabase",
            "azure",
            "digitalocean",
        )
    )
    qs = parse_qs(parsed.query)
    if cloud_host and "ssl" not in qs and "sslmode" not in qs:
        qs["ssl"] = ["require"]
        url = urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in qs.items()})))
    return url


settings = get_settings()
_db_url = _normalize_db_url(settings.database_url)
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
# asyncpg: ssl via query param works on SQLAlchemy 2; also pass connect_args for require
if "ssl=require" in _db_url or "sslmode=require" in _db_url:
    _engine_kwargs["connect_args"] = {"ssl": True}

engine = create_async_engine(_db_url, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
