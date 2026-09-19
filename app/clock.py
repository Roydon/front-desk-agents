"""Fixed demo clock (NFR-4). Never call datetime.now() directly elsewhere."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.settings import settings

TZ = ZoneInfo(settings.tz)


def now() -> datetime:
    """Demo 'current time': DEMO_TODAY at 08:00 in the configured timezone."""
    d = date.fromisoformat(settings.demo_today)
    return datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=TZ)


def today() -> date:
    return now().date()
