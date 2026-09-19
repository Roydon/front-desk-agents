"""Deterministic guards that run before (and partly after) the model. Never move to a prompt."""

from __future__ import annotations

import re
from functools import lru_cache

import yaml
from pydantic import BaseModel

from app.settings import settings


@lru_cache(maxsize=1)
def _escalation() -> dict:
    return yaml.safe_load((settings.config_dir / "escalation.yaml").read_text())


class GuardResult(BaseModel):
    safety_hits: list[str] = []
    injection: bool = False
    injection_pattern: str | None = None
    card_found: bool = False
    redacted_text: str


# --- safety --------------------------------------------------------------
def safety_hits(text: str) -> list[str]:
    hits: list[str] = []
    for kw in _escalation().get("safety_keywords", []):
        pattern = r"(?<!\w)" + re.escape(str(kw)) + r"(?!\w)"
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(str(kw))
    return hits


# --- prompt injection ----------------------------------------------------
def injection_match(text: str) -> str | None:
    for pat in _escalation().get("prompt_injection_patterns", []):
        if re.search(pat, text, re.IGNORECASE):
            return pat
    return None


# --- card data -----------------------------------------------------------
def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_EXP_RE = re.compile(r"\bexp(?:iry|iration)?\.?\s*:?\s*\d{1,2}\s*/\s*\d{2,4}\b", re.IGNORECASE)
_CVV_RE = re.compile(r"\b(?:cvv|cvc|cid)\s*:?\s*\d{3,4}\b", re.IGNORECASE)


def redact_card(text: str) -> tuple[str, bool]:
    found = False

    def _sub(m: re.Match) -> str:
        nonlocal found
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found = True
            return "[card removed]"
        return m.group(0)

    out = _CARD_RE.sub(_sub, text)
    if found:
        out = _EXP_RE.sub("[card removed]", out)
        out = _CVV_RE.sub("[card removed]", out)
        out = re.sub(r"\[card removed\](?:\s+[a-z]{2,4}\s+)?(?:\s*\[card removed\])+", "[card removed]", out)
    return out, found


def run_guards(text: str) -> GuardResult:
    redacted, card = redact_card(text)
    return GuardResult(
        safety_hits=safety_hits(text),
        injection=injection_match(redacted) is not None,
        injection_pattern=injection_match(redacted),
        card_found=card,
        redacted_text=redacted,
    )
