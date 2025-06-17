from __future__ import annotations

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Project-wide configuration loaded from environment variables (.env optional)."""

    # General settings
    PORT: int = Field(8000, description="HTTP port for MCP server")
    LOG_LEVEL: str = Field("DEBUG", description="Root log level for Loguru")

    # LLM / Ollama
    OLLAMA_BASE_URL: HttpUrl = Field("http://localhost:11434", description="Base URL of the local Ollama server")
    LLM_MODEL: str = Field("qwen3:8b", description="Model name passed to Ollama")
    TEMPERATURE: float = Field(0.5, description="LLM sampling temperature")
    MAX_TOOLS_ITERATIONS: int = Field(15, description="Max reasoning/tool iterations per user prompt")

    # UI (CLI) options
    UI_THEME: str = Field("dark", description="CLI theme (dark/light)")
    SHOW_THOUGHTS: bool = Field(True, description="Whether to stream the model's <think> content")

    # Security
    MCP_HMAC_KEY: str = Field("dev-secret", description="Shared secret used to sign/verify tool results")

    # Database
    SESSION_DB_PATH: str = Field("ape/sessions.db", description="Path to SQLite database that stores message history")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings() 