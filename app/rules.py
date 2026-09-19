"""decide(): deterministic routing after the guards and the model. First match wins."""

from __future__ import annotations

import re
from functools import lru_cache

import yaml
from pydantic import BaseModel

from app.connectors.bookings import SqliteBookings
from app.guards import GuardResult
from app.llm.base import TriageResult
from app.settings import settings

RECOGNISED_DOC_KINDS = {"insurance_cert", "vessel_registration", "signed_contract"}
_QUERY_HINTS = ["?", "make sure", "did you", "got it", "confirm", "checking", "let me know"]


@lru_cache(maxsize=1)
def _escalation() -> dict:
    return yaml.safe_load((settings.config_dir / "escalation.yaml").read_text())


@lru_cache(maxsize=1)
def _routing() -> dict:
    return yaml.safe_load((settings.config_dir / "routing.yaml").read_text())


class DecisionResult(BaseModel):
    decision: str  # alert | human | draft | record_update | ignore
    team: str = "office"
    reason: str | None = None
    rule_id: str | None = None


def _draft_team(triage: TriageResult) -> str:
    routing = _routing()
    # Seasonal-slip matters are the dockmaster's, whether phrased as a booking or a question.
    if triage.fields.unit_type == "seasonal_slip":
        return "dockmaster"
    if triage.intent == "new_booking":
        block = routing.get("new_booking", {})
        ut = triage.fields.unit_type
        return block.get(ut, block.get("default", "office"))
    val = routing.get(triage.intent, "office")
    return val if isinstance(val, str) else "office"


def _has_recognised_attachment(message: dict) -> bool:
    return any(a.get("kind") in RECOGNISED_DOC_KINDS for a in message.get("attachments", []))


def _looks_like_query(text: str) -> bool:
    low = text.lower()
    return any(h in low for h in _QUERY_HINTS)


def decide(
    message: dict,
    guards: GuardResult,
    triage: TriageResult,
    bookings: SqliteBookings,
) -> DecisionResult:
    esc = _escalation()
    text = guards.redacted_text

    # 1. pre-model safety keyword
    if guards.safety_hits:
        s = esc["safety"]
        return DecisionResult(decision="alert", team=s["team"], reason="safety", rule_id="safety")

    # 2. card data
    if guards.card_found:
        return DecisionResult(decision="human", team="office", reason="card_data", rule_id="card_data")

    # 3. prompt injection
    if guards.injection:
        return DecisionResult(
            decision="human",
            team="office",
            reason="suspicious_instructions",
            rule_id="suspicious_instructions",
        )

    # 4. model said safety
    if triage.intent == "safety_urgent":
        return DecisionResult(decision="alert", team="dockmaster", reason="safety", rule_id="safety")

    # 5a. low confidence gate (ahead of the generic vendor/other rule)
    if triage.confidence < esc.get("low_confidence_threshold", 0.70):
        return DecisionResult(decision="human", team="office", reason="low_confidence", rule_id="low_confidence")

    # 5b. escalation rules from config, first match wins
    for rule in esc.get("rules", []):
        if rule["id"] == "low_confidence":
            continue  # handled above
        if _rule_matches(rule, message, text, triage, bookings):
            return DecisionResult(
                decision=rule["action"],
                team=rule.get("team", "office"),
                reason=rule["id"],
                rule_id=rule["id"],
            )

    # 6. record update (document intent)
    if triage.intent == "documents" and triage.fields.reservation_id:
        if _has_recognised_attachment(message) or not _looks_like_query(text):
            return DecisionResult(decision="record_update", team="office", reason=None)

    # 7. spam
    if triage.intent == "other" and triage.spam:
        return DecisionResult(decision="ignore", team="office", reason="spam", rule_id="spam")

    # 8. otherwise draft
    return DecisionResult(decision="draft", team=_draft_team(triage), reason=None)


def _rule_matches(rule: dict, message: dict, text: str, triage: TriageResult, bookings: SqliteBookings) -> bool:
    cond = rule["when"]
    if "intent" in cond and triage.intent != cond["intent"]:
        return False
    if "text_matches" in cond and not re.search(cond["text_matches"], text, re.IGNORECASE):
        return False
    if "spam" in cond and triage.spam != cond["spam"]:
        return False
    if "units_requested_gt" in cond:
        if not (triage.fields.units_requested and triage.fields.units_requested > cond["units_requested_gt"]):
            return False
    if "urgency_in" in cond and triage.urgency not in cond["urgency_in"]:
        return False
    if "confidence_lt" in cond and not (triage.confidence < cond["confidence_lt"]):
        return False
    if "sender_reservation_unit_type" in cond:
        res = bookings.get_reservation(
            reservation_id=triage.fields.reservation_id,
            email=message.get("from_email"),
            phone=message.get("from_phone"),
        )
        if not res or res.unit_type != cond["sender_reservation_unit_type"]:
            return False
    return True
