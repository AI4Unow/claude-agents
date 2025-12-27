"""Configuration settings for Modal agents."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Z.AI (GLM-4.7)
    zai_api_key: str = ""
    zai_model: str = "glm-4.7"
    zai_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # Telegram
    telegram_bot_token: str = ""

    # Firebase
    firebase_project_id: str = ""
    firebase_credentials: str = ""

    # GitHub (optional)
    github_token: str = ""

    # Qdrant Cloud
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
