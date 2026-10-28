from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aicr_user:aicr_password@localhost:5432/aicr_db"
    DATABASE_URL_SYNC: str = "postgresql://aicr_user:aicr_password@localhost:5432/aicr_db"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_REST_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334

    # Webhook Secrets
    GITHUB_WEBHOOK_SECRET: str = "test_github_secret"
    GITLAB_WEBHOOK_SECRET: str = "test_gitlab_secret"

    # OpenAI / LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
