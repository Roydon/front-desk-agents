"""Run the real pipeline against an ad-hoc message, without touching the demo data.

This powers the "try it yourself" page: a visitor pastes a voicemail transcript or an email
and sees exactly what the agents would do - guards, triage, the rule that fired, the tools
called, the draft and its grounding check.

Nothing is persisted to `messages`/`drafts`, so the scripted demo counts stay reproducible.
One `events` row is written so the activity log still shows that it happened.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.agents import drafter
from app.agents.triage import run_triage
from app.connectors.bookings import SqliteBookings
from app.guards import run_guards
from app.llm.factory import get_provider
from app.rules import decide
from app.settings import settings
from app.store.db import log_event

TRY_ID = "TRY"


class TryResult(BaseModel):
    channel: str
    body_redacted: str
    guards: dict
    triage: dict | None = None
    decision: str
    team: str
    reason: str | None = None
    rule_id: str | None = None
    draft_text: str | None = None
    policy_ids: list[str] = []
    tool_calls: list[dict] = []
    grounding: dict = {}
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    provider: str = ""
    note: str | None = None


def run_try(
    session,
    *,
    channel: str,
    body: str,
    subject: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    from_phone: str | None = None,
) -> TryResult:
    """Full pipeline, read-only against the demo data."""
    provider = get_provider()
    bookings = SqliteBookings(session)
    guards = run_guards(body)

    raw = {
        "message_id": TRY_ID,
        "channel": channel,
        "received_at": None,
        "from_name": from_name,
        "from_email": from_email,
        "from_phone": from_phone,
        "subject": subject,
        "body": body,
        "body_redacted": guards.redacted_text,
        "attachments": [],
        "expected": {},
    }

    guard_view = {
        "safety_hits": guards.safety_hits,
        "card_found": guards.card_found,
        "injection": guards.injection,
        "injection_pattern": guards.injection_pattern,
    }

    triage, resp, fail = run_triage(provider, raw)
    if fail or triage is None:
        from app.agents import triage as triage_mod

        detail = triage_mod.last_error or "no detail"
        result = TryResult(
            channel=channel,
            body_redacted=guards.redacted_text,
            guards=guard_view,
            decision="human",
            team="office",
            reason="triage_failed",
            provider=settings.llm_provider,
            note=f"Triage could not classify this message, so it goes to a person. ({detail})",
        )
        _log(session, result)
        return result

    d = decide(raw, guards, triage, bookings)
    result = TryResult(
        channel=channel,
        body_redacted=guards.redacted_text,
        guards=guard_view,
        triage=triage.model_dump(),
        decision=d.decision,
        team=d.team,
        reason=d.reason,
        rule_id=d.rule_id,
        model=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        latency_ms=resp.latency_ms,
        provider=settings.llm_provider,
    )

    if d.decision == "draft":
        outcome = drafter.compose(raw, triage, bookings)
        if outcome.kind == "defer":
            result.decision = "human"
            result.reason = outcome.defer_reason
            result.rule_id = outcome.defer_reason
            result.draft_text = outcome.text or None
            result.grounding = outcome.grounding
            result.tool_calls = outcome.tool_calls
        else:
            result.draft_text = outcome.text
            result.policy_ids = outcome.policy_ids
            result.tool_calls = outcome.tool_calls
            result.grounding = outcome.grounding

    if settings.llm_provider == "fake":
        result.note = (
            "The offline FakeProvider only replays recorded triage for the 35 scripted messages, "
            "so an ad-hoc message falls through to a person. Set LLM_PROVIDER=openrouter to see "
            "the live model classify this text."
        )

    _log(session, result)
    return result


def _log(session, result: TryResult) -> None:
    log_event(
        session,
        action="try_it",
        agent="tryit",
        message_id=TRY_ID,
        detail={
            "channel": result.channel,
            "decision": result.decision,
            "reason": result.reason,
            "intent": (result.triage or {}).get("intent"),
            "grounded": result.grounding.get("passed"),
        },
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )
    session.commit()
