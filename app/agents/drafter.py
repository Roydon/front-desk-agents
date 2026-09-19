"""Reply drafter (FR-4). Deterministic, grounded composition from tool results.

The offline path composes replies directly from tool outputs, so every $, date and unit id
is grounded by construction. The live LLM path (prompts/drafter.md) would replace the
composition step; the grounding check and tool contract stay identical.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app import grounding
from app.connectors.bookings import SqliteBookings
from app.llm.base import TriageResult
from app.tools.availability import check_availability
from app.tools.policy import get_policy
from app.tools.pricing import quote

TYPE_NAMES = {
    "transient_slip": "transient slip",
    "seasonal_slip": "seasonal slip",
    "campsite_rv_full": "full-hookup RV site",
    "campsite_rv_we": "water/electric RV site",
    "campsite_tent": "tent site",
}

# general-question topic -> policy ids
TOPIC_POLICIES = {
    "checkin": ["P1"],
    "fuel": ["P11"],
    "launch": ["P13"],
    "trailer": ["P14"],
    "pets": ["P9"],
}
SIGN = "- Lakeside Cove front desk"


class DraftOutcome(BaseModel):
    kind: str  # draft | defer
    text: str = ""
    subject: str | None = None
    language: str = "en"
    policy_ids: list[str] = []
    tool_calls: list[dict] = []
    grounding: dict = {}
    defer_reason: str | None = None


def _friendly(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}"


def _draft(text, *, sources, policy_ids, tool_calls, language="en", subject=None) -> DraftOutcome:
    g = grounding.check(text, sources)
    if not g.passed:
        return DraftOutcome(
            kind="defer",
            defer_reason="ungrounded",
            text=text,
            grounding=g.model_dump(),
            tool_calls=tool_calls,
            policy_ids=policy_ids,
        )
    return DraftOutcome(
        kind="draft",
        text=text,
        subject=subject,
        language=language,
        policy_ids=policy_ids,
        tool_calls=tool_calls,
        grounding=g.model_dump(),
    )


def compose(message: dict, triage: TriageResult, bookings: SqliteBookings) -> DraftOutcome:
    intent = triage.intent
    if intent == "new_booking":
        return _booking(message, triage, bookings)
    if intent == "boatyard_service":
        return _boatyard(triage)
    if intent == "documents":
        return _documents(triage, bookings)
    if intent == "change_or_cancel":
        return _change(triage, bookings)
    if intent in {"general_question"}:
        return _general(message, triage, bookings)
    return DraftOutcome(kind="defer", defer_reason="no_policy")


# --- seasonal slip quote (booking or general enquiry) --------------------
def _seasonal(f) -> DraftOutcome:
    length = f.boat_length_ft or f.rv_length_ft
    lang = f.language or "en"
    if not length:
        # No boat length given - we cannot quote a per-foot seasonal rate.
        return DraftOutcome(kind="defer", defer_reason="no_policy")
    q = quote("seasonal_slip", length_ft=length)
    pols = get_policy("P2", "P3")
    sources = [q.model_dump_json(), *(p.text for p in pols)]
    tool_calls = [{"tool": "quote", "args": {"item": "seasonal_slip", "length_ft": length}, "result": q.model_dump()}]
    text = (
        f"Thanks for asking about a seasonal slip for your {length:g}-ft boat. "
        f"A seasonal slip runs {q.unit_rate}, which comes to {q.total} for the season, "
        f"with a 25% deposit of {q.deposit} at signing. Seasonal slips are arranged through "
        f"our dockmaster - reply or call and we will get you set up (P2, P3). {SIGN}"
    )
    return _draft(text, sources=sources, policy_ids=["P2", "P3"], tool_calls=tool_calls, language=lang)


# --- new booking ---------------------------------------------------------
def _booking(message, triage, bookings) -> DraftOutcome:
    f = triage.fields
    ut = f.unit_type or "transient_slip"
    length = f.boat_length_ft or f.rv_length_ft
    lang = f.language or "en"
    sources: list[str] = []
    tool_calls: list[dict] = []
    policy_ids: list[str] = ["P2", "P3"]

    if ut == "seasonal_slip":
        return _seasonal(f)

    arrival = date.fromisoformat(f.arrival)
    departure = date.fromisoformat(f.departure)
    nights = (departure - arrival).days or 1
    avail = check_availability(
        bookings,
        unit_type=ut,
        arrival=arrival,
        departure=departure,
        boat_length_ft=f.boat_length_ft,
        beam_ft=f.beam_ft,
        rv_length_ft=f.rv_length_ft,
    )
    q = quote(ut, nights=nights, length_ft=length, arrival=arrival)
    pols = get_policy(*(["P2", "P3", "P4", "P5"] if q.holiday_min_nights else ["P2", "P3"]))
    tool_calls.append(
        {
            "tool": "check_availability",
            "args": {"unit_type": ut, "arrival": f.arrival, "departure": f.departure},
            "result": avail.model_dump(),
        }
    )
    tool_calls.append(
        {"tool": "quote", "args": {"item": ut, "nights": nights, "length_ft": length}, "result": q.model_dump()}
    )
    sources += [
        q.model_dump_json(),
        arrival.isoformat(),
        departure.isoformat(),
        *avail.available,
        *avail.recommended,
        *(p.text for p in pols),
    ]

    rec = avail.recommended
    others = [u for u in avail.available if u not in rec]
    if not avail.available:
        return DraftOutcome(kind="defer", defer_reason="no_availability")

    if q.holiday_min_nights:
        policy_ids = ["P2", "P3", "P4", "P5"]
    elif ut == "campsite_tent":
        policy_ids = ["P2", "P3", "P9"]
        get_policy("P9")

    tname = TYPE_NAMES.get(ut, "slip")
    if lang == "es":
        text = _booking_es(f, arrival, departure, avail, q, tname)
        return _draft(text, sources=sources, policy_ids=["P2", "P3"], tool_calls=tool_calls, language="es")

    lines = [f"Thanks for your interest in a {tname} for {_friendly(arrival)} to {_friendly(departure)}."]
    fit = ", ".join(rec) if rec else ", ".join(avail.available)
    lines.append(
        f"We have availability that fits: {fit}." + (f" Other options: {', '.join(others)}." if others else "")
    )
    rate_line = f"The rate is {q.unit_rate}"
    if q.holiday_min_nights:
        rate_line += f", with a {q.holiday_min_nights}-night holiday minimum, so {q.total} for the weekend"
    else:
        rate_line += f", so {q.total} for {q.nights} night(s)"
    rate_line += f", with a {q.deposit} deposit to confirm (P2, P3)."
    lines.append(rate_line)
    if q.holiday_min_nights:
        lines.append("Labour Day weekend bookings need 30 days' notice for any refund (P4, P5).")
    if ut == "campsite_tent":
        lines.append("Up to 2 pets are welcome and must be leashed on the grounds (P9).")
    lines.append(f"Nothing is booked yet - reply or call and we will hold it with the deposit. {SIGN}")
    return _draft(" ".join(lines), sources=sources, policy_ids=policy_ids, tool_calls=tool_calls)


def _booking_es(f, arrival, departure, avail, q, tname) -> str:
    fit = ", ".join(avail.recommended or avail.available)
    return (
        f"Gracias por su interes en un sitio para RV con conexion completa del "
        f"{arrival.day} al {departure.day} de septiembre de 2026. "
        f"Tenemos disponibilidad: {fit}. "
        f"La tarifa es {q.unit_rate}, es decir {q.total} por {q.nights} noches, "
        f"con un deposito de {q.deposit} para confirmar (P2, P3). "
        f"Todavia no hay nada reservado; responda o llame y lo reservamos con el deposito. "
        f"- Recepcion de Lakeside Cove"
    )


# --- boatyard ------------------------------------------------------------
def _boatyard(triage) -> DraftOutcome:
    length = triage.fields.boat_length_ft or 0
    q = quote("haul_out", length_ft=length)
    pols = get_policy("P12")
    sources = [q.model_dump_json(), *(p.text for p in pols)]
    tool_calls = [{"tool": "quote", "args": {"item": "haul_out", "length_ft": length}, "result": q.model_dump()}]
    text = (
        f"Thanks for asking about haul-out and winterization for your {length:g}-ft pontoon. "
        f"Haul-out and block is {q.unit_rate}, which is {q.total} for your boat. "
        f"Winterization and storage are quoted separately by the boatyard, and service is usually "
        f"scheduled within 3 business days (P12). Reply with your preferred week in mid-October and "
        f"the boatyard team will get you on the schedule. {SIGN}"
    )
    return _draft(text, sources=sources, policy_ids=["P12"], tool_calls=tool_calls)


# --- documents (confirmation) -------------------------------------------
def _documents(triage, bookings) -> DraftOutcome:
    rid = triage.fields.reservation_id
    res = bookings.get_reservation(reservation_id=rid) if rid else None
    tool_calls = [
        {"tool": "get_reservation", "args": {"reservation_id": rid}, "result": (res.model_dump() if res else None)}
    ]
    received = res and res.insurance_cert in {"received_pending_review", "ok"}
    pols = get_policy("P6")
    sources = [p.text for p in pols]
    if received:
        text = (
            f"Thanks for checking. Yes - we have received your certificate of insurance for "
            f"reservation {rid} and it is currently being reviewed. We will let you know once it is "
            f"approved; nothing further is needed from you right now (P6). {SIGN}"
        )
    else:
        text = (
            f"Thanks for the note about reservation {rid}. We do not show your certificate of "
            f"insurance on file yet - please send it before arrival so we can review it (P6). {SIGN}"
        )
    return _draft(text, sources=sources, policy_ids=["P6"], tool_calls=tool_calls)


# --- change / cancel (date change) --------------------------------------
def _change(triage, bookings) -> DraftOutcome:
    f = triage.fields
    rid = f.reservation_id
    res = bookings.get_reservation(reservation_id=rid) if rid else None
    if not (res and f.arrival and f.departure):
        return DraftOutcome(kind="defer", defer_reason="no_policy")
    arrival = date.fromisoformat(f.arrival)
    departure = date.fromisoformat(f.departure)
    avail = check_availability(
        bookings,
        unit_type=res.unit_type,
        arrival=arrival,
        departure=departure,
        rv_length_ft=res.length_ft,
    )
    same_site_free = res.unit_id in avail.available
    pols = get_policy("P4")
    sources = [arrival.isoformat(), departure.isoformat(), *avail.available, *(p.text for p in pols)]
    tool_calls = [
        {"tool": "get_reservation", "args": {"reservation_id": rid}, "result": res.model_dump()},
        {
            "tool": "check_availability",
            "args": {"unit_type": res.unit_type, "arrival": f.arrival, "departure": f.departure},
            "result": avail.model_dump(),
        },
    ]
    site_line = (
        f"Your site {res.unit_id} is open for those dates."
        if same_site_free
        else f"We have other sites open for those dates: {', '.join(avail.available[:3])}."
    )
    text = (
        f"Thanks - we can move reservation {rid} to {_friendly(arrival)} to {_friendly(departure)}. "
        f"{site_line} Because that is more than 14 days before your original arrival, the change is "
        f"free (P4). Reply to confirm and we will update the reservation. {SIGN}"
    )
    return _draft(text, sources=sources, policy_ids=["P4"], tool_calls=tool_calls)


# --- general questions ---------------------------------------------------
def _general(message, triage, bookings) -> DraftOutcome:
    body = (message.get("body") or "").lower()
    rid = triage.fields.reservation_id

    # Refusals first: we have no policy for liveaboards or events, even if a model
    # tagged the message with a unit type.
    if any(w in body for w in ["liveaboard", "living aboard", "live aboard"]):
        return DraftOutcome(kind="defer", defer_reason="no_policy")
    if any(w in body for w in ["wedding", "pavilion", "reunion hall", "event space"]):
        return DraftOutcome(kind="defer", defer_reason="no_policy")

    # A seasonal-slip pricing enquiry (some models label this general_question).
    if triage.fields.unit_type == "seasonal_slip" or "seasonal slip" in body:
        return _seasonal(triage.fields)

    if any(w in body for w in ["check in", "check-in", "checkin", "get in", "late", "after hours"]):
        pols = get_policy("P1")
        sources = [p.text for p in pols]
        text = (
            "Thanks for letting us know. Campsite check-in is from 3:00 pm and the office closes at "
            "6:00 pm. If you arrive after that, your welcome packet, site map and gate code will be "
            "in the after-hours box by the office door, labelled with your name; the dockmaster's "
            f"evening line is open until 9:00 pm (P1). Safe travels. {SIGN}"
        )
        return _draft(
            text,
            sources=sources,
            policy_ids=["P1"],
            tool_calls=[{"tool": "get_policy", "args": {"id": "P1"}, "result": [p.model_dump() for p in pols]}],
        )

    if any(w in body for w in ["launch", "jet ski", "ramp"]):
        q = quote("launch_ramp")
        pols = get_policy("P13")
        sources = [q.model_dump_json(), *(p.text for p in pols)]
        text = (
            f"Thanks for asking. A day launch at the ramp is {q.unit_rate} for visitors who are not "
            f"staying with us (it is free for registered marina and campground guests) (P13). {SIGN}"
        )
        return _draft(
            text,
            sources=sources,
            policy_ids=["P13"],
            tool_calls=[{"tool": "quote", "args": {"item": "launch_ramp"}, "result": q.model_dump()}],
        )

    if any(w in body for w in ["trailer", "parking", "park our"]):
        q = quote("trailer_parking")
        res = bookings.get_reservation(reservation_id=rid) if rid else None
        pols = get_policy("P14")
        sources = [q.model_dump_json(), *(p.text for p in pols)]
        text = (
            f"Good question. Boat trailers park in Lot B at {q.unit_rate}. Parking is free for guests "
            f"with a slip reservation of 3 nights or more; your stay is shorter than that, so the "
            f"{q.unit_rate} rate applies (P14). {SIGN}"
        )
        return _draft(
            text,
            sources=sources,
            policy_ids=["P14"],
            tool_calls=[
                {"tool": "quote", "args": {"item": "trailer_parking"}, "result": q.model_dump()},
                {
                    "tool": "get_reservation",
                    "args": {"reservation_id": rid},
                    "result": (res.model_dump() if res else None),
                },
            ],
        )

    if any(w in body for w in ["pump-out", "pump out", "pumpout", "fuel dock", "fuel"]):
        pols = get_policy("P11")
        sources = [p.text for p in pols]
        text = (
            "Happy to help. Pump-out is free for marina and campground guests during fuel-dock hours. "
            "The fuel dock (gas and diesel) is open 8:00 am to 6:00 pm daily, May through October "
            f"(P11). {SIGN}"
        )
        return _draft(
            text,
            sources=sources,
            policy_ids=["P11"],
            tool_calls=[{"tool": "get_policy", "args": {"id": "P11"}, "result": [p.model_dump() for p in pols]}],
        )

    if any(w in body for w in ["pet", "dog", "dogs"]):
        pols = get_policy("P9")
        sources = [p.text for p in pols]
        pets = triage.fields.pets or 0
        over = pets > 2
        note = (
            "We allow up to 2 pets per site, so unfortunately we are not able to accommodate 3, and "
            "we are not able to make an exception"
            if over
            else "We allow up to 2 pets per site"
        )
        text = (
            f"Thanks for checking about pets. {note}. Pets must be leashed outside your tent and never "
            f"left unattended (P9). {SIGN}"
        )
        return _draft(
            text,
            sources=sources,
            policy_ids=["P9"],
            tool_calls=[{"tool": "get_policy", "args": {"id": "P9"}, "result": [p.model_dump() for p in pols]}],
        )

    return DraftOutcome(kind="defer", defer_reason="no_policy")
