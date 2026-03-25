from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="zoom-rtms-local-prototype", alias="APP_NAME")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    zoom_client_id: str = Field(default="", alias="ZOOM_CLIENT_ID")
    zoom_client_secret: str = Field(default="", alias="ZOOM_CLIENT_SECRET")
    zoom_webhook_secret_token: str = Field(default="", alias="ZOOM_WEBHOOK_SECRET_TOKEN")

    webhook_path: str = Field(default="/webhook", alias="WEBHOOK_PATH")
    recordings_dir: Path = Field(default=Path("recordings"), alias="RECORDINGS_DIR")

    audio_sample_rate: int = Field(default=48000, alias="AUDIO_SAMPLE_RATE")
    audio_channels: int = Field(default=2, alias="AUDIO_CHANNELS")
    audio_sample_width_bytes: int = Field(default=2, alias="AUDIO_SAMPLE_WIDTH_BYTES")


settings = Settings()
