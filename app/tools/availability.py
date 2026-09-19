"""check_availability() - fitting, free units and the recommended (smallest fitting) class."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from app.connectors.bookings import SqliteBookings


def _sortkey(unit_id: str):
    m = re.match(r"([A-Za-z]+)(\d+)", unit_id)
    return (m.group(1), int(m.group(2))) if m else (unit_id, 0)


class Availability(BaseModel):
    unit_type: str
    arrival: str
    departure: str
    available: list[str]
    recommended: list[str]
    excluded: dict[str, str] = {}


def check_availability(
    bookings: SqliteBookings,
    *,
    unit_type: str,
    arrival: date,
    departure: date,
    boat_length_ft: float | None = None,
    beam_ft: float | None = None,
    rv_length_ft: float | None = None,
) -> Availability:
    length = boat_length_ft or rv_length_ft
    occupied = bookings.occupied_units(unit_type, arrival, departure)
    units = sorted(bookings.units_of_type(unit_type), key=lambda u: _sortkey(u.unit_id))

    fitting: list = []
    excluded: dict[str, str] = {}
    for u in units:
        if length and u.max_length_ft is not None and u.max_length_ft < length:
            excluded[u.unit_id] = f"max {u.max_length_ft:g} ft < {length:g} ft"
            continue
        if beam_ft and u.max_beam_ft is not None and u.max_beam_ft < beam_ft:
            excluded[u.unit_id] = f"max beam {u.max_beam_ft:g} ft < {beam_ft:g} ft"
            continue
        fitting.append(u)

    available_units = [u for u in fitting if u.unit_id not in occupied]
    for u in fitting:
        if u.unit_id in occupied:
            excluded[u.unit_id] = "occupied for those dates"

    available = [u.unit_id for u in available_units]

    # recommended = free units in the smallest size class (by max_length_ft) that fits
    recommended: list[str] = []
    if available_units:
        classes = sorted({u.max_length_ft for u in fitting if u.max_length_ft is not None})
        if classes:
            smallest = classes[0]
            recommended = [u.unit_id for u in available_units if u.max_length_ft == smallest]
        else:  # no length dimension (tents): recommend all available
            recommended = available

    return Availability(
        unit_type=unit_type,
        arrival=arrival.isoformat(),
        departure=departure.isoformat(),
        available=available,
        recommended=recommended,
        excluded=excluded,
    )
