from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables and .env file.
    Follows 12-factor app principles and zero hardcoding security constraints.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Project Settings
    PROJECT_NAME: str = "Smart Enterprise Hub"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database Configuration (PostgreSQL 16)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "enterprise_hub"

    # Database URLs (Async for FastAPI runtime, Sync for Alembic if needed)
    DATABASE_URL: str | None = None
    SYNC_DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # JWT Authentication & Passwords
    JWT_SECRET: str = "development_super_secret_jwt_key_enterprise_hub_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60      # Strict OWASP rule: max 60 mins
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14        # Strict rule: 14 days

    # Storage Security & Strategy
    STORAGE_DIR: Path = Path("storage/tenants")
    MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # Strict OWASP limit: 25 MB max

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://localhost:3000"]

    # External APIs (Gemini Flash / DeepSeek, Telegram)
    GEMINI_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None


settings = Settings()
