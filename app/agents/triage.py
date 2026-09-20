"""Triage agent: run the provider, return a validated TriageResult + usage."""

from __future__ import annotations

import logging

from app.llm.base import LLMResponse, TriageResult

log = logging.getLogger(__name__)

# Set when triage last failed, so callers (and the UI) can show why instead of a bare
# "triage_failed". Routing never depends on this - a failure always goes to a person.
last_error: str | None = None


def run_triage(provider, message: dict) -> tuple[TriageResult | None, LLMResponse, str | None]:
    """Returns (result, response, failure_reason). failure_reason set only on failure."""
    global last_error
    try:
        result, resp = provider.triage(message)
        last_error = None
        return result, resp, None
    except Exception as exc:  # noqa: BLE001 - any provider failure routes to a person
        last_error = f"{type(exc).__name__}: {exc}"
        log.warning("triage failed for %s: %s", message.get("message_id"), last_error)
        resp = LLMResponse(text="", model=getattr(provider, "name", "unknown"))
        return None, resp, "triage_failed"
