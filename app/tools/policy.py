"""get_policy() - parses config/policies.md by '## P<n>' headings."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel

from app.settings import settings


class PolicySection(BaseModel):
    id: str
    title: str
    text: str


@lru_cache(maxsize=1)
def _sections() -> dict[str, PolicySection]:
    text = (settings.config_dir / "policies.md").read_text()
    out: dict[str, PolicySection] = {}
    pattern = re.compile(r"^##\s+(P\d+)\s+(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        pid, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[pid] = PolicySection(id=pid, title=title, text=text[start:end].strip())
    return out


def get_policy(*ids: str) -> list[PolicySection]:
    """Return policy sections by id (P1..P14). Unknown ids are skipped."""
    sections = _sections()
    return [sections[i] for i in ids if i in sections]
