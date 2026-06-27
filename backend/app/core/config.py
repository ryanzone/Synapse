"""
Core configuration module for Synapse backend.

Loads all settings from environment variables or .env file using
pydantic-settings with full type validation.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Synapse application settings.

    All values are loaded from environment variables or a .env file.
    Defaults are provided for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LM Studio
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="Base URL for the LM Studio OpenAI-compatible API.",
    )
    lmstudio_api_key: str = Field(
        default="lm-studio",
        description="API key for LM Studio (arbitrary value for local usage).",
    )

    # Model identifiers
    default_model: str = Field(
        default="qwen3-4b-instruct",
        description="Default reasoning model identifier.",
    )
    vision_model: str = Field(
        default="qwen3-vl-4b-instruct",
        description="Vision-capable model identifier.",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model identifier.",
    )

    # Qdrant
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector database connection URL.",
    )
    qdrant_collection: str = Field(
        default="synapse_memory",
        description="Qdrant collection name for long-term memory.",
    )

    # n8n
    n8n_url: str = Field(
        default="http://localhost:5678",
        description="Base URL for the n8n workflow engine.",
    )
    n8n_api_key: str = Field(
        default="",
        description="API key for authenticating with n8n.",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging verbosity level (DEBUG, INFO, WARNING, ERROR).",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure log level is one of the accepted Loguru levels."""
        allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{value}'")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Using lru_cache ensures the .env file is parsed exactly once
    per process lifetime.
    """
    return Settings()