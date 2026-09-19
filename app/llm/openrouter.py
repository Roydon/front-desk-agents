"""OpenRouter provider (OpenAI-compatible). Used for the hosted demo.

Speaks https://openrouter.ai/api/v1/chat/completions. We keep a portable JSON contract
(model returns a single JSON object) rather than relying on native tool calling, so the
pinned model stays swappable.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

from app.clock import today
from app.llm import cache
from app.llm.base import LLMResponse, TriageResult
from app.settings import settings

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "triage.md").read_text()


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(0))


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self) -> None:
        self.model = settings.openrouter_model
        self.api_key = settings.openrouter_api_key

    def _system(self) -> str:
        return _PROMPT.replace("{{TODAY}}", today().isoformat())

    def _user(self, message: dict) -> str:
        m = {k: message.get(k) for k in ("channel", "from_name", "subject")}
        m["body"] = message.get("body_redacted") or message.get("body")
        return json.dumps(m, ensure_ascii=False)

    def _call(self, system: str, user: str) -> LLMResponse:
        cached = cache.get([self.name, self.model, system, user])
        if cached:
            return LLMResponse(**cached)
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        started = time.time()
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        out = LLMResponse(
            text=data["choices"][0]["message"]["content"],
            model=self.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=int((time.time() - started) * 1000),
        )
        cache.put([self.name, self.model, system, user], out.model_dump())
        return out

    def triage(self, message: dict) -> tuple[TriageResult, LLMResponse]:
        system, user = self._system(), self._user(message)
        resp = self._call(system, user)
        try:
            return TriageResult(**_extract_json(resp.text)), resp
        except Exception as exc:  # noqa: BLE001 - one retry with the error appended
            retry = self._call(system, f"{user}\n\nYour last output was invalid: {exc}. Return only valid JSON.")
            return TriageResult(**_extract_json(retry.text)), retry
