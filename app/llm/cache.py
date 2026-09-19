"""Tiny on-disk JSON cache for LLM responses (survives rate limits / outages)."""

from __future__ import annotations

import hashlib
import json

from app.settings import settings

_CACHE_DIR = settings.var_dir / "llm_cache"


def _key(parts: list[str]) -> str:
    h = hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()
    return h[:32]


def get(parts: list[str]) -> dict | None:
    if not settings.llm_cache:
        return None
    path = _CACHE_DIR / f"{_key(parts)}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def put(parts: list[str], value: dict) -> None:
    if not settings.llm_cache:
        return
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (_CACHE_DIR / f"{_key(parts)}.json").write_text(json.dumps(value))
