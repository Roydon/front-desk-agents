"""Select the configured LLM provider."""

from __future__ import annotations

from app.llm.fake import FakeProvider
from app.settings import settings


def get_provider():
    provider = settings.llm_provider.lower()
    if provider == "fake":
        return FakeProvider()
    if provider == "openrouter":
        from app.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider()
    # ollama / anthropic would plug in here (same TriageResult contract).
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r}")
