"""Deterministic offline provider: replays the recorded triage stored on each message.

This is the spec's FakeProvider. In tests and the offline demo it returns the labelled
triage from data/messages.jsonl (the 'expected' block), so routing is identical every run.
The live model path (OpenRouter/Ollama/Anthropic) produces the same TriageResult shape.
"""

from __future__ import annotations

from app.llm.base import LLMResponse, TriageFields, TriageResult


def _summary(message: dict) -> str:
    body = (message.get("body") or "").strip().replace("\n", " ")
    words = body.split()
    text = " ".join(words[:22])
    if len(words) > 22:
        text += "..."
    return text


class FakeProvider:
    name = "fake"

    def triage(self, message: dict) -> tuple[TriageResult, LLMResponse]:
        expected = message.get("expected") or {}
        reason = expected.get("reason")
        confidence = 0.55 if reason == "low_confidence" else 0.98
        spam = reason == "spam"
        fields = TriageFields(**(expected.get("fields") or {}))
        result = TriageResult(
            intent=expected.get("intent", "other"),
            urgency=expected.get("urgency", "routine"),
            team=expected.get("team", "office"),
            fields=fields,
            summary=_summary(message),
            confidence=confidence,
            spam=spam,
        )
        resp = LLMResponse(
            text="[recorded]",
            model="fake",
            input_tokens=len((message.get("body") or "").split()),
            output_tokens=12,
            latency_ms=0,
        )
        return result, resp
