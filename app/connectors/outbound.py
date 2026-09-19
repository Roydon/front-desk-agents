"""Outbound connector. Demo impl writes a file; there is no real email/SMS client.

Production: Gmail send / SMTP; Twilio SMS.
"""

from __future__ import annotations

from typing import Literal, Protocol

from app.clock import now
from app.settings import settings


class OutboundConnector(Protocol):
    def send(self, *, draft_id: int, to: str, channel: str, subject: str, text: str) -> str: ...


class FileOutbound:
    def __init__(self) -> None:
        self.dir = settings.var_dir / "outbox"

    def send(
        self,
        *,
        draft_id: int,
        to: str,
        channel: Literal["email", "sms"],
        subject: str,
        text: str,
    ) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"draft_{draft_id}.txt"
        headers = [
            f"Channel: {channel}",
            f"To: {to}",
            f"Subject: {subject}",
            f"Sent-At: {now().isoformat()}",
            "",
        ]
        path.write_text("\n".join(headers) + text + "\n")
        return str(path)
