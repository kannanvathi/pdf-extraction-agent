from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # ── Active provider ──────────────────────────────────────────────────
    active_provider: Literal["openai", "gemini", "anthropic", "llamaparse", "liteparse"] = "llamaparse"

    # ── API keys (fill whichever providers you want to use) ──────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # ── LlamaParse provider ──────────────────────────────────────────────
    llama_cloud_api_key: str = ""

    # ── Infrastructure ───────────────────────────────────────────────────
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "pdf_agent"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    upload_dir: str = "/tmp/pdf_uploads"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Human-readable provider info exposed to the frontend
PROVIDER_REGISTRY = {
    "llamaparse": {
        "label": "LlamaParse",
        "models": ["markdown", "text"],
        "color": "violet",
    },
    "liteparse": {
        "label": "LiteParse",
        "models": ["default"],
        "color": "teal",
        "local": True,           # no API key — availability checked at runtime
    },
    "openai": {
        "label": "OpenAI",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        "color": "green",
    },
    "gemini": {
        "label": "Google Gemini",
        "models": ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"],
        "color": "blue",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "models": ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-opus-4-6"],
        "color": "purple",
    },
}

