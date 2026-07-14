"""Normalize Railway/Heroku DATABASE_URL for async SQLAlchemy."""
import os
import sys


def normalize(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


if __name__ == "__main__":
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        print("DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    print(normalize(raw))
