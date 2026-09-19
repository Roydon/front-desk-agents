"""Alert connector. Demo impl writes to console + var/outbox/alerts/.

Production: SMS + phone call to the on-duty dockmaster; Slack/Teams if used.
"""

from __future__ import annotations

from typing import Protocol

from app.clock import now
from app.settings import settings


class AlertConnector(Protocol):
    def raise_alert(self, *, message_id: str, team: str, callback: str, summary: str) -> str: ...


class ConsoleFileAlerts:
    def __init__(self) -> None:
        self.dir = settings.var_dir / "outbox" / "alerts"

    def raise_alert(self, *, message_id: str, team: str, callback: str, summary: str) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{message_id}.txt"
        body = f"ALERT to {team}\nTime: {now().isoformat()}\nMessage: {message_id}\nCallback: {callback}\n\n{summary}\n"
        path.write_text(body)
        print(f"[ALERT -> {team}] {message_id}: {summary} (callback {callback})")
        return str(path)
