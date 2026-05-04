from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Incident Management System"
    app_version: str = "1.0.0"
    env: str = "development"
    secret_key: str = "change_me_in_production"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ims_user:ims_secret@localhost:5432/ims_db"

    # Redis
    redis_url: str = "redis://:ims_redis_secret@localhost:6379/0"

    # SQLite (raw signal lake)
    sqlite_path: str = "./signals.db"

    # Rate limiting
    rate_limit_signals: str = "1000/minute"

    # Queue
    queue_max_size: int = 50_000
    worker_count: int = 4

    # Metrics
    metrics_interval_seconds: int = 5

    # Debounce
    debounce_window_seconds: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
