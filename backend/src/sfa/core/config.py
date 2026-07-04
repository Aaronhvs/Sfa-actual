from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sfa:sfa@localhost:5432/sfa"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    INGEST_INTERVAL_MINUTES: int = 30

    # External APIs
    API_FOOTBALL_KEY: str = ""
    API_FOOTBALL_BASE_URL: str = "https://v3.football.api-sports.io"

    # Admin API key — empty string disables the check (dev only)
    # In production, must be set or all /admin requests are blocked
    ADMIN_API_KEY: str = ""

    # AI ranking explanations. If disabled or no API key is configured, SFA
    # writes deterministic Spanish explanations from the same evidence package.
    AI_EXPLANATIONS_ENABLED: bool = False
    AI_EXPLANATIONS_PROVIDER: str = "deterministic"
    AI_EXPLANATIONS_API_KEY: str = ""
    AI_EXPLANATIONS_BASE_URL: str = ""
    AI_EXPLANATIONS_MODEL: str = "gpt-5-nano"
    AI_EXPLANATIONS_TIMEOUT_SECONDS: int = 20
    AI_EXPLANATIONS_TOP_N: int = 10
    AI_EXPLANATIONS_PROMPT_VERSION: str = "ranking-explanation-v1"
    AI_EXPLANATIONS_MAX_INPUT_TOKENS_PER_PLAYER: int = 1800
    AI_EXPLANATIONS_MAX_OUTPUT_TOKENS_PER_PLAYER: int = 700
    AI_EXPLANATIONS_DAILY_BUDGET_USD: float = 2.0

    # CORS — comma-separated origins allowed to call the API
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
