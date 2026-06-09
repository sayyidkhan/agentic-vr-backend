from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="SceneVerse AI Backend", alias="APP_NAME")
    sceneverse_profile: str = Field(default="local", alias="SCENEVERSE_PROFILE")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    database_url: str = Field(default="sqlite:///./data/sceneverse.db", alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(default="amazon.nova-lite-v1:0", alias="BEDROCK_MODEL_ID")
    bedrock_api_key: Optional[str] = Field(default=None, alias="AWS_BEARER_TOKEN_BEDROCK")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_realtime_transcription_model: str = Field(
        default="gpt-4o-transcribe",
        alias="OPENAI_REALTIME_TRANSCRIPTION_MODEL",
    )
    openai_realtime_token_ttl_seconds: int = Field(default=600, alias="OPENAI_REALTIME_TOKEN_TTL_SECONDS")
    openai_realtime_vad_threshold: float = Field(default=0.5, alias="OPENAI_REALTIME_VAD_THRESHOLD")
    openai_realtime_vad_prefix_padding_ms: int = Field(
        default=300,
        alias="OPENAI_REALTIME_VAD_PREFIX_PADDING_MS",
    )
    openai_realtime_vad_silence_duration_ms: int = Field(
        default=800,
        alias="OPENAI_REALTIME_VAD_SILENCE_DURATION_MS",
    )
    model_registry_path: str = Field(default="app/data/enabled_models.json", alias="MODEL_REGISTRY_PATH")
    enable_live_scene_analysis: bool = Field(default=False, alias="ENABLE_LIVE_SCENE_ANALYSIS")
    scene_analysis_model_id: str = Field(default="global.anthropic.claude-sonnet-4-6", alias="SCENE_ANALYSIS_MODEL_ID")
    enable_exa_character_enrichment: bool = Field(default=True, alias="ENABLE_EXA_CHARACTER_ENRICHMENT")
    scene_analysis_max_characters: int = Field(default=4, alias="SCENE_ANALYSIS_MAX_CHARACTERS")
    enable_live_character_chat: bool = Field(default=False, alias="ENABLE_LIVE_CHARACTER_CHAT")
    character_chat_model_id: str = Field(
        default="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        alias="CHARACTER_CHAT_MODEL_ID",
    )
    exa_api_key: Optional[str] = Field(default=None, alias="EXA_API_KEY")
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_currency: str = Field(default="sgd", alias="STRIPE_CURRENCY")
    stripe_unlock_amount_cents: int = Field(default=500, alias="STRIPE_UNLOCK_AMOUNT_CENTS")
    media_storage_backend: str = Field(default="local", alias="MEDIA_STORAGE_BACKEND")
    media_local_dir: str = Field(default="./data/media", alias="MEDIA_LOCAL_DIR")
    media_public_path: str = Field(default="/media", alias="MEDIA_PUBLIC_PATH")
    media_storage_prefix: str = Field(default="videos", alias="MEDIA_STORAGE_PREFIX")
    s3_video_bucket: Optional[str] = Field(default=None, alias="S3_VIDEO_BUCKET")
    media_cdn_base_url: Optional[str] = Field(default=None, alias="MEDIA_CDN_BASE_URL")
    local_database_url: Optional[str] = Field(default=None, alias="LOCAL_DATABASE_URL")
    local_media_local_dir: Optional[str] = Field(default=None, alias="LOCAL_MEDIA_LOCAL_DIR")
    local_media_public_path: Optional[str] = Field(default=None, alias="LOCAL_MEDIA_PUBLIC_PATH")
    local_media_storage_prefix: Optional[str] = Field(default=None, alias="LOCAL_MEDIA_STORAGE_PREFIX")
    cloud_database_url: Optional[str] = Field(default=None, alias="CLOUD_DATABASE_URL")
    cloud_media_local_dir: Optional[str] = Field(default=None, alias="CLOUD_MEDIA_LOCAL_DIR")
    cloud_media_public_path: Optional[str] = Field(default=None, alias="CLOUD_MEDIA_PUBLIC_PATH")
    cloud_media_storage_prefix: Optional[str] = Field(default=None, alias="CLOUD_MEDIA_STORAGE_PREFIX")
    cloud_s3_video_bucket: Optional[str] = Field(default=None, alias="CLOUD_S3_VIDEO_BUCKET")
    cloud_media_cdn_base_url: Optional[str] = Field(default=None, alias="CLOUD_MEDIA_CDN_BASE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    def model_post_init(self, __context: object) -> None:
        profile = self.sceneverse_profile.strip().lower()
        if profile not in {"local", "cloud"}:
            raise ValueError("SCENEVERSE_PROFILE must be either 'local' or 'cloud'")

        self.sceneverse_profile = profile
        self.environment = profile

        if profile == "cloud":
            self.database_url = self.cloud_database_url or self.database_url
            self.media_storage_backend = "s3"
            self.media_local_dir = self.cloud_media_local_dir or self.media_local_dir
            self.media_public_path = self.cloud_media_public_path or self.media_public_path
            self.media_storage_prefix = self.cloud_media_storage_prefix or self.media_storage_prefix
            self.s3_video_bucket = self.cloud_s3_video_bucket or self.s3_video_bucket
            self.media_cdn_base_url = self.cloud_media_cdn_base_url or self.media_cdn_base_url
            return

        self.database_url = self.local_database_url or self.database_url
        self.media_storage_backend = "local"
        self.media_local_dir = self.local_media_local_dir or self.media_local_dir
        self.media_public_path = self.local_media_public_path or self.media_public_path
        self.media_storage_prefix = self.local_media_storage_prefix or self.media_storage_prefix
        self.s3_video_bucket = None
        self.media_cdn_base_url = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
