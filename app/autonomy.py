"""Autonomy readiness: turn measured staff edits into a per-category auto-send verdict.

The bid promises autonomy is raised in stages "based on measured edit rates, not assumed".
This is that measurement. A category only graduates when enough drafts have been reviewed,
almost none were rejected, and staff barely changed the wording.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlmodel import select

from app.store.models import Draft, TriageRow

# Thresholds. Deliberately conservative - this gates unsupervised guest contact.
MIN_REVIEWED = 10  # below this we simply do not have evidence
MAX_REJECT_RATE = 0.05
MAX_AVG_EDIT = 0.05  # normalised Levenshtein distance
MIN_CLEAN_RATE = 0.90  # share approved with no edit at all
CLOSE_AVG_EDIT = 0.15

REVIEWED_STATUSES = {"approved", "sent", "rejected"}


class CategoryReadiness(BaseModel):
    category: str
    reviewed: int
    approved: int
    rejected: int
    clean: int  # approved with zero edits
    avg_edit: float
    clean_rate: float
    reject_rate: float
    verdict: str
    verdict_class: str  # ready | close | hold | nodata
    explanation: str


def _verdict(reviewed: int, reject_rate: float, avg_edit: float, clean_rate: float) -> tuple[str, str, str]:
    if reviewed < MIN_REVIEWED:
        return (
            "Not enough data",
            "nodata",
            f"Only {reviewed} of {MIN_REVIEWED} reviews needed. Keep approving until we have evidence.",
        )
    if reject_rate > MAX_REJECT_RATE:
        return (
            "Keep approving",
            "hold",
            f"{reject_rate:.0%} of drafts were rejected (limit {MAX_REJECT_RATE:.0%}). Not safe to relax.",
        )
    if avg_edit <= MAX_AVG_EDIT and clean_rate >= MIN_CLEAN_RATE:
        return (
            "Ready for auto-send",
            "ready",
            f"{clean_rate:.0%} sent unchanged and the average edit is {avg_edit:.1%}. "
            "Safe to send this category without approval, with spot checks.",
        )
    if avg_edit <= CLOSE_AVG_EDIT:
        return (
            "Close - keep approving",
            "close",
            f"Average edit is {avg_edit:.1%}; staff still reword these. Review a little longer.",
        )
    return (
        "Keep approving",
        "hold",
        f"Average edit is {avg_edit:.1%} - staff rewrite these substantially. Needs prompt or policy work.",
    )


def readiness(session) -> list[CategoryReadiness]:
    """One row per category (reply intent, plus chaser reminders)."""
    intents = {t.message_id: (t.result or {}).get("intent", "unknown") for t in session.exec(select(TriageRow)).all()}
    buckets: dict[str, list[Draft]] = {}
    for d in session.exec(select(Draft)).all():
        if d.status not in REVIEWED_STATUSES:
            continue
        key = "document reminder" if d.kind == "reminder" else intents.get(d.message_id, "unknown")
        buckets.setdefault(key, []).append(d)

    out: list[CategoryReadiness] = []
    for category, drafts in sorted(buckets.items()):
        reviewed = len(drafts)
        rejected = sum(1 for d in drafts if d.status == "rejected")
        approved = reviewed - rejected
        sent = [d for d in drafts if d.status != "rejected"]
        edits = [d.edit_distance for d in sent if d.edit_distance is not None]
        clean = sum(1 for e in edits if e == 0)
        avg_edit = (sum(edits) / len(edits)) if edits else 0.0
        clean_rate = (clean / len(edits)) if edits else 0.0
        reject_rate = rejected / reviewed if reviewed else 0.0
        verdict, klass, explanation = _verdict(reviewed, reject_rate, avg_edit, clean_rate)
        out.append(
            CategoryReadiness(
                category=category,
                reviewed=reviewed,
                approved=approved,
                rejected=rejected,
                clean=clean,
                avg_edit=round(avg_edit, 3),
                clean_rate=round(clean_rate, 3),
                reject_rate=round(reject_rate, 3),
                verdict=verdict,
                verdict_class=klass,
                explanation=explanation,
            )
        )
    return out
