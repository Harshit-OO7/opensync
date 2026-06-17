"""
Application configuration.
All settings are loaded from environment variables (or .env file).
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Application ─────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production"
    LOG_LEVEL: str = "INFO"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        if self.APP_ENV == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return []

    # ─── Database ────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://opensync:opensync@localhost:5432/opensync"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ─── Redis ───────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── Qdrant ──────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_REPOS: str = "repositories"

    # ─── GitHub ──────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REQUESTS_PER_HOUR: int = 5000
    GITHUB_GRAPHQL_REQUESTS_PER_HOUR: int = 5000

    # ─── ML ──────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 32

    # ─── LLM ─────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_MAX_TOKENS: int = 1000

    # ─── Frontend ────────────────────────────────────────
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """
    Return cached settings instance.
    In tests, call get_settings.cache_clear() to reload.
    """
    return Settings()


settings = get_settings()
