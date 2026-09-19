"""Triage agent: run the provider, return a validated TriageResult + usage."""

from __future__ import annotations

from app.llm.base import LLMResponse, TriageResult


def run_triage(provider, message: dict) -> tuple[TriageResult, LLMResponse, str | None]:
    """Returns (result, response, failure_reason). failure_reason set only on validation failure."""
    try:
        result, resp = provider.triage(message)
        return result, resp, None
    except Exception:  # noqa: BLE001 - provider does its own single retry; treat as triage_failed
        resp = LLMResponse(text="", model=getattr(provider, "name", "unknown"))
        return None, resp, "triage_failed"
