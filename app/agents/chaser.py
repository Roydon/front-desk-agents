"""Document chaser (FR-5). Runs after the inbox. Config: config/chaser.yaml."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

import yaml
from pydantic import BaseModel
from sqlmodel import Session, select

from app import grounding
from app.clock import now
from app.connectors.bookings import SqliteBookings
from app.settings import settings
from app.store.models import Draft
from app.tools.payments import payment_link

SIGN = "- Lakeside Cove front desk"


@lru_cache(maxsize=1)
def _cfg() -> dict:
    return yaml.safe_load((settings.config_dir / "chaser.yaml").read_text())


class ChaserReminder(BaseModel):
    reservation_id: str
    guest_name: str
    email: str | None
    arrival: str
    missing: list[str]
    text: str
    policy_ids: list[str]
    grounding: dict


class ChaserSkip(BaseModel):
    reservation_id: str
    reason: str


def _friendly(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}"


def _within_hours(iso_ts: str | None, hours: int) -> bool:
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return (now() - ts) <= timedelta(hours=hours)


def _already_reminded_today(session: Session, rid: str) -> bool:
    rows = session.exec(select(Draft).where(Draft.reservation_id == rid, Draft.kind == "reminder"))
    return any(r for r in rows)


def run_chaser(session: Session, bookings: SqliteBookings) -> tuple[list[ChaserReminder], list[ChaserSkip]]:
    cfg = _cfg()
    received = set(cfg["received_statuses"])
    labels = cfg["item_labels"]
    quiet_hours = cfg["quiet_if_guest_contact_within_hours"]

    reminders: list[ChaserReminder] = []
    skips: list[ChaserSkip] = []

    for offset in cfg["offsets_days"]:
        target: date = now().date() + timedelta(days=offset)
        for res in bookings.reservations_arriving(target):
            required = cfg["required_items"].get(res.unit_type, [])
            if not required:
                continue  # seasonal etc: never chased
            missing = [i for i in required if getattr(res, i) not in received]
            recently_received = [i for i in required if getattr(res, i) == "received_pending_review"]

            if _within_hours(res.last_guest_contact, quiet_hours):
                skips.append(ChaserSkip(reservation_id=res.reservation_id, reason="guest_contacted"))
                continue
            if not missing and recently_received:
                skips.append(ChaserSkip(reservation_id=res.reservation_id, reason="document_received"))
                continue
            if not missing:
                continue  # nothing missing and nothing recently received: not considered
            if _already_reminded_today(session, res.reservation_id):
                skips.append(ChaserSkip(reservation_id=res.reservation_id, reason="already_reminded"))
                continue

            item_text = ", ".join(labels[i] for i in missing)
            pay_line = ""
            if "deposit_paid" in missing:
                pay_line = f" You can pay the first-night deposit here: {payment_link(res.reservation_id)}."
            text = (
                f"Hi {res.guest_name.split()[0]}, we are getting ready for your arrival on "
                f"{_friendly(res.arrival)}. Before then we still need: {item_text}.{pay_line} "
                f"Reply to this note or call the office and we will take care of it. Thank you. {SIGN}"
            )
            policy_ids = sorted({labels[i].split("(")[-1].rstrip(")") for i in missing if "(" in labels[i]})
            g = grounding.check(text, [res.arrival])
            reminders.append(
                ChaserReminder(
                    reservation_id=res.reservation_id,
                    guest_name=res.guest_name,
                    email=res.email,
                    arrival=res.arrival,
                    missing=missing,
                    text=text,
                    policy_ids=policy_ids,
                    grounding=g.model_dump(),
                )
            )
    return reminders, skips
