from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Apparel Line Balancing API"
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/line_balancing"

    jwt_secret: str = "change-me-in-production-please-32-chars-min"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    solver_time_limit_s: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
