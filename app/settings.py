"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "fake"

    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.0-flash-001"

    ollama_model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"

    anthropic_api_key: str = ""
    anthropic_triage_model: str = "claude-haiku-4-5-20251001"
    anthropic_draft_model: str = "claude-sonnet-5"

    llm_cache: bool = True

    app_user: str = ""
    app_password: str = ""

    demo_today: str = "2026-08-24"
    tz: str = "America/New_York"

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"

    @property
    def config_dir(self) -> Path:
        return REPO_ROOT / "config"

    @property
    def var_dir(self) -> Path:
        return REPO_ROOT / "var"

    @property
    def db_path(self) -> Path:
        return self.var_dir / "app.db"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.app_user and self.app_password)


settings = Settings()
