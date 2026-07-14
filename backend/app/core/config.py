from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Hybrid providers
    inference_mode: str = "hybrid"  # local | cloud | hybrid
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_enabled: bool = True
    # Best local roles given installed models (tools + thinking)
    ollama_planner_model: str = "deepseek-r1:8b"
    ollama_executor_model: str = "llama3.1:8b"
    ollama_critic_model: str = "deepseek-r1:8b"
    ollama_summarizer_model: str = "llama3.1:8b"
    ollama_chat_model: str = "qwen2.5:32b-instruct"
    ollama_seed_model: str = "qwen2.5:3b"
    ollama_nexus_model: str = "llama3.1:8b"
    ollama_sovereign_model: str = "llama3.1:70b"

    xai_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    xai_planner_model: str = "grok-4.5"
    xai_executor_model: str = "grok-4.3"
    xai_critic_model: str = "grok-4.5"
    xai_embedding_model: str = "text-embedding-3-small"

    # Sellable API platform
    platform_name: str = "AstraCortex API"
    default_token_balance: int = 1_000_000
    token_markup_per_1k: float = 0.002

    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,"
        "capacitor://localhost,http://localhost,https://*.vercel.app"
    )
    upload_dir: str = "./data/uploads"
    database_url: str = "postgresql+asyncpg://astra:astra@localhost:5432/astracortex"
    redis_url: str = "redis://localhost:6379/0"
    # Railway / cloud often injects PORT
    port: int = 8000
    public_api_url: str = "http://localhost:8000"
    allow_cors_all: bool = True
    embedding_dim: int = 1536
    semantic_write_threshold: float = 0.65
    default_step_budget: int = 12
    default_token_budget: int = 50_000
    human_like_system: bool = True
    product_tier_default: str = "nexus"  # seed | nexus | sovereign

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
