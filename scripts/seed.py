"""Reset the SQLite database and load data/ (units, reservations, messages)."""

from __future__ import annotations

import csv

from app.connectors.inbox import JsonlInbox
from app.settings import settings
from app.store.db import get_session, log_event, reset_db
from app.store.models import Message, Reservation, Unit


def _num(v: str):
    v = (v or "").strip()
    return float(v) if v else None


def seed() -> dict:
    reset_db()
    counts = {"units": 0, "reservations": 0, "messages": 0}
    with get_session() as session:
        with open(settings.data_dir / "units.csv") as f:
            for row in csv.DictReader(f):
                session.add(
                    Unit(
                        unit_id=row["unit_id"],
                        unit_type=row["unit_type"],
                        max_length_ft=_num(row["max_length_ft"]),
                        max_beam_ft=_num(row["max_beam_ft"]),
                        power=row["power"] or None,
                        notes=row["notes"] or None,
                    )
                )
                counts["units"] += 1

        with open(settings.data_dir / "reservations.csv") as f:
            for row in csv.DictReader(f):
                session.add(
                    Reservation(
                        reservation_id=row["reservation_id"],
                        guest_name=row["guest_name"],
                        email=row["email"] or None,
                        phone=row["phone"] or None,
                        unit_type=row["unit_type"],
                        unit_id=row["unit_id"] or None,
                        arrival=row["arrival"],
                        departure=row["departure"],
                        vessel_name=row["vessel_name"] or None,
                        length_ft=_num(row["length_ft"]),
                        beam_ft=_num(row["beam_ft"]),
                        insurance_cert=row["insurance_cert"],
                        vessel_registration=row["vessel_registration"],
                        signed_contract=row["signed_contract"],
                        deposit_paid=row["deposit_paid"],
                        last_guest_contact=row["last_guest_contact"] or None,
                        status=row["status"],
                    )
                )
                counts["reservations"] += 1

        for raw in JsonlInbox().fetch_new():
            session.add(
                Message(
                    message_id=raw["message_id"],
                    channel=raw["channel"],
                    received_at=raw["received_at"],
                    from_name=raw.get("from_name"),
                    from_phone=raw.get("from_phone"),
                    from_email=raw.get("from_email"),
                    subject=raw.get("subject"),
                    body=raw.get("body") or "",
                    attachments=raw.get("attachments", []),
                    expected=raw.get("expected", {}),
                    status="new",
                )
            )
            counts["messages"] += 1

        log_event(session, action="seed", agent="seed", detail=counts)
        session.commit()
    return counts


if __name__ == "__main__":
    c = seed()
    print(f"Seeded {c['messages']} messages, {c['units']} units, {c['reservations']} reservations.")
