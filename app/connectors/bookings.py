"""Bookings connector. Demo impl backed by SQLite.

Production: the client's booking platform API (unknown - confirm in discovery).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from sqlmodel import Session, select

from app.store.models import Reservation, Unit


def _overlaps(a_arr: str, a_dep: str, b_arr: str, b_dep: str) -> bool:
    # arrival < other.departure and departure > other.arrival (departure day is free)
    return a_arr < b_dep and a_dep > b_arr


class BookingsConnector(Protocol):
    def occupied_units(self, unit_type: str, arrival: date, departure: date) -> set[str]: ...
    def get_reservation(self, **kw) -> Reservation | None: ...


class SqliteBookings:
    def __init__(self, session: Session) -> None:
        self.session = session

    def units_of_type(self, unit_type: str) -> list[Unit]:
        return list(self.session.exec(select(Unit).where(Unit.unit_type == unit_type)))

    def occupied_units(self, unit_type: str, arrival: date, departure: date) -> set[str]:
        arr, dep = arrival.isoformat(), departure.isoformat()
        occ: set[str] = set()
        rows = self.session.exec(select(Reservation).where(Reservation.unit_type == unit_type))
        for r in rows:
            if r.status in {"cancelled"}:
                continue
            if r.unit_id and _overlaps(arr, dep, r.arrival, r.departure):
                occ.add(r.unit_id)
        return occ

    def get_reservation(self, *, reservation_id=None, email=None, phone=None) -> Reservation | None:
        if reservation_id:
            return self.session.get(Reservation, reservation_id)
        stmt = select(Reservation)
        if email:
            stmt = stmt.where(Reservation.email == email)
        elif phone:
            stmt = stmt.where(Reservation.phone == phone)
        else:
            return None
        return self.session.exec(stmt).first()

    def reservations_arriving(self, on: date) -> list[Reservation]:
        return list(self.session.exec(select(Reservation).where(Reservation.arrival == on.isoformat())))

    def update_documents(self, reservation_id: str, **items: str) -> None:
        r = self.session.get(Reservation, reservation_id)
        if not r:
            return
        for k, v in items.items():
            setattr(r, k, v)
        self.session.add(r)

    def record_guest_contact(self, reservation_id: str, at: str) -> None:
        r = self.session.get(Reservation, reservation_id)
        if r:
            r.last_guest_contact = at
            self.session.add(r)
