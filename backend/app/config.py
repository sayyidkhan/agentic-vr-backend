from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="SceneVerse AI Backend", alias="APP_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    database_url: str = Field(default="sqlite:///./data/sceneverse.db", alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    exa_api_key: Optional[str] = Field(default=None, alias="EXA_API_KEY")
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
