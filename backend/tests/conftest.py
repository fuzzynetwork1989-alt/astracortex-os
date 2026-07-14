import os

# Force offline-friendly defaults for unit tests
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INFERENCE_MODE", "local")
os.environ.setdefault("XAI_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6399/15")
