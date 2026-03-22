from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    secret_key: str = Field(
        default="development-only-secret-key-replace-in-production-min-32-chars-long",
        description="Set SECRET_KEY in production environments.",
    )
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    password_reset_expire_minutes: int = 60
    environment: str = "development"
    log_level: str = "INFO"
    # Comma-separated origins for browser clients (no spaces). Override with CORS_ORIGINS in production if needed.
    cors_origins: str = (
        "http://localhost:3001,http://localhost:5000,"
        "https://bank-sphere-admin-8n5hcld2q-suryanshvns-projects.vercel.app,"
        "https://bank-sphere.vercel.app"
    )


settings = Settings()
