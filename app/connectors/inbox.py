"""Inbox connector. Demo impl reads data/messages.jsonl.

Production: Gmail API / IMAP for email; Twilio/RingCentral recording webhook + transcription
for voicemail. Same InboundMessage shape.
"""

from __future__ import annotations

import json
from typing import Protocol

from app.settings import settings


class InboxConnector(Protocol):
    def fetch_new(self) -> list[dict]: ...


class JsonlInbox:
    def __init__(self, path=None) -> None:
        self.path = path or (settings.data_dir / "messages.jsonl")

    def fetch_new(self) -> list[dict]:
        rows: list[dict] = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        rows.sort(key=lambda m: m["received_at"])
        return rows
