from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    grpc_address: str = "[::]:50052"

    gateway_identity_rpc_token: str

    database_url: str
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"

    access_token_private_key_path: Path
    access_token_issuer: str = "jurion-identity"
    access_token_audience: str = "jurion-api"
    access_token_ttl_seconds: int = 600

    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30

    login_attempt_limit: int = 5
    login_attempt_window_seconds: int = 900

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
