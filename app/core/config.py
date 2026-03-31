from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./creator_engine.db"

    # Anthropic
    anthropic_api_key: str = ""

    # SearchAPI.io (env var kept as serper_api_key for compat)
    serper_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Redis
    redis_url: str = ""

    # ClickUp
    clickup_api_token: str = ""

    # Apify
    apify_api_token: str = ""

    # App
    app_secret_key: str = "change-this"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,https://*.up.railway.app"
    env: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def effective_database_url(self) -> str:
        """
        Handle Railway's DATABASE_URL format.
        Railway gives: postgresql://user:pass@host:port/db
        SQLAlchemy async needs: postgresql+asyncpg://user:pass@host:port/db
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache()
def get_settings() -> Settings:
    return Settings()
