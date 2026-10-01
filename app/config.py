from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_database_url: str = "sqlite:///./control.db"

    auth_issuer: str = "http://localhost:9000"
    auth_audience: str = "database-mcp"

    max_query_rows: int = Field(default=500, ge=1, le=50_000)
    query_timeout_seconds: int = Field(default=5, ge=1, le=60)
    max_result_size_mb: int = Field(default=5, ge=1, le=100)

    credential_encryption_key: str = "dev-only-change-this-key-32-bytes"


@lru_cache
def get_settings() -> Settings:
    return Settings()
