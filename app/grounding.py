"""Grounding check: every $ amount, date and unit id in a draft must appear in tool results."""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparser
from pydantic import BaseModel

from app.clock import today

_MONEY_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\$\s?\d+(?:\.\d{2})?")
_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
    "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_MONTH_DATE_RE = re.compile(rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b", re.IGNORECASE)
_UNIT_RE = re.compile(r"\b(?:RV\d{1,2}|D\d|S\d{1,2}|T\d)\b")


class GroundingResult(BaseModel):
    passed: bool
    unmatched: list[str] = []


def _money(text: str) -> set[str]:
    out = set()
    for m in _MONEY_RE.findall(text):
        val = float(m.replace("$", "").replace(",", "").strip())
        out.add(f"{val:.2f}")
    return out


def _dates(text: str) -> set[str]:
    out = set()
    for m in _ISO_RE.findall(text):
        out.add(m)
    base = datetime(today().year, today().month, 1)
    for m in _MONTH_DATE_RE.findall(text):
        try:
            d = dateparser.parse(m, default=base)
            out.add(d.date().isoformat())
        except (ValueError, OverflowError):
            pass
    return out


def _units(text: str) -> set[str]:
    return set(_UNIT_RE.findall(text))


def check(draft_text: str, sources: list[str]) -> GroundingResult:
    src = "\n".join(sources)
    src_money, src_dates, src_units = _money(src), _dates(src), _units(src)
    unmatched: list[str] = []
    for amt in _money(draft_text):
        if amt not in src_money:
            unmatched.append(f"${amt}")
    for d in _dates(draft_text):
        if d not in src_dates:
            unmatched.append(d)
    for u in _units(draft_text):
        if u not in src_units:
            unmatched.append(u)
    return GroundingResult(passed=not unmatched, unmatched=unmatched)
