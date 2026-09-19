"""get_reservation() - thin wrapper over the bookings connector."""

from __future__ import annotations

from app.connectors.bookings import SqliteBookings
from app.store.models import Reservation


def get_reservation(bookings: SqliteBookings, **kw) -> Reservation | None:
    return bookings.get_reservation(**kw)
