"""Orchestration: run_inbox(), run_chaser(), run_all(). Every step writes an events row."""

from __future__ import annotations

from sqlmodel import select

from app.agents import drafter
from app.agents.chaser import run_chaser as _run_chaser
from app.agents.triage import run_triage
from app.clock import now
from app.connectors.alerts import ConsoleFileAlerts
from app.connectors.bookings import SqliteBookings
from app.guards import run_guards
from app.llm.factory import get_provider
from app.rules import RECOGNISED_DOC_KINDS, decide
from app.store.db import get_session, log_event
from app.store.models import Alert, Decision, Draft, Message, TriageRow


def _raw_of(msg: Message) -> dict:
    return {
        "message_id": msg.message_id,
        "channel": msg.channel,
        "received_at": msg.received_at,
        "from_name": msg.from_name,
        "from_phone": msg.from_phone,
        "from_email": msg.from_email,
        "subject": msg.subject,
        "body": msg.body,
        "attachments": msg.attachments or [],
        "expected": msg.expected or {},
    }


def _subject_for(message: dict) -> str:
    if message.get("subject"):
        subj = message["subject"]
        return subj if subj.lower().startswith("re:") else f"Re: {subj}"
    return "Your message to Lakeside Cove"


def run_inbox() -> dict:
    provider = get_provider()
    counts = {"draft": 0, "human": 0, "alert": 0, "record_update": 0, "ignore": 0, "in": 0}

    with get_session() as session:
        bookings = SqliteBookings(session)
        alerts = ConsoleFileAlerts()

        pending = session.exec(select(Message).where(Message.status == "new")).all()
        pending.sort(key=lambda m: m.received_at)

        for msg in pending:
            raw = _raw_of(msg)
            counts["in"] += 1
            guards = run_guards(msg.body or "")
            msg.body_redacted = guards.redacted_text
            if guards.card_found:
                msg.body = guards.redacted_text  # never keep card data, even in the raw column
            session.add(msg)
            log_event(
                session, action="intake", agent="inbox", message_id=msg.message_id, detail={"channel": msg.channel}
            )
            if guards.safety_hits:
                log_event(
                    session,
                    action="guard_hit",
                    agent="guards",
                    message_id=msg.message_id,
                    detail={"safety": guards.safety_hits},
                )
            if guards.card_found:
                log_event(
                    session,
                    action="guard_hit",
                    agent="guards",
                    message_id=msg.message_id,
                    detail={"card_redacted": True},
                )
            if guards.injection:
                log_event(
                    session,
                    action="guard_hit",
                    agent="guards",
                    message_id=msg.message_id,
                    detail={"injection": guards.injection_pattern},
                )

            # pass redacted text to the model
            model_message = {**raw, "body_redacted": guards.redacted_text}
            triage, resp, fail = run_triage(provider, model_message)
            if fail:
                session.add(Decision(message_id=msg.message_id, decision="human", reason="triage_failed"))
                msg.status = "needs_person"
                log_event(session, action="triage_failed", agent="triage", message_id=msg.message_id)
                counts["human"] += 1
                session.commit()
                continue

            session.add(
                TriageRow(
                    message_id=msg.message_id,
                    result=triage.model_dump(),
                    model=resp.model,
                    prompt_version="triage-v1",
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    latency_ms=resp.latency_ms,
                )
            )
            log_event(
                session,
                action="triage",
                agent="triage",
                message_id=msg.message_id,
                detail={"intent": triage.intent, "confidence": triage.confidence},
                model=resp.model,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                cost_usd=_cost(resp),
            )

            d = decide(raw, guards, triage, bookings)
            session.add(
                Decision(
                    message_id=msg.message_id, decision=d.decision, team=d.team, reason=d.reason, rule_id=d.rule_id
                )
            )
            log_event(
                session,
                action="decision",
                agent="rules",
                message_id=msg.message_id,
                detail={"decision": d.decision, "reason": d.reason, "team": d.team},
            )

            if d.decision == "alert":
                callback = msg.from_phone or msg.from_email or "unknown"
                session.add(
                    Alert(
                        message_id=msg.message_id,
                        team=d.team,
                        callback=callback,
                        summary=triage.summary,
                        created_at=now().isoformat(),
                    )
                )
                alerts.raise_alert(message_id=msg.message_id, team=d.team, callback=callback, summary=triage.summary)
                log_event(session, action="alert", agent="rules", message_id=msg.message_id, detail={"team": d.team})
                msg.status = "alert"
                counts["alert"] += 1

            elif d.decision == "record_update":
                _apply_record_update(session, bookings, raw, triage)
                msg.status = "record_update"
                counts["record_update"] += 1

            elif d.decision == "ignore":
                msg.status = "ignored"
                log_event(
                    session, action="ignore", agent="rules", message_id=msg.message_id, detail={"reason": d.reason}
                )
                counts["ignore"] += 1

            elif d.decision == "human":
                msg.status = "needs_person"
                counts["human"] += 1

            elif d.decision == "draft":
                outcome = drafter.compose(raw, triage, bookings)
                if outcome.kind == "defer":
                    # the drafter found no policy / failed grounding: escalate to a person
                    _set_decision_human(session, msg.message_id, outcome.defer_reason, d.team)
                    msg.status = "needs_person"
                    log_event(
                        session,
                        action="draft_deferred",
                        agent="drafter",
                        message_id=msg.message_id,
                        detail={"reason": outcome.defer_reason, "grounding": outcome.grounding},
                    )
                    counts["human"] += 1
                else:
                    draft = Draft(
                        message_id=msg.message_id,
                        kind="reply",
                        team=d.team,
                        subject=_subject_for(raw),
                        text=outcome.text,
                        language=outcome.language,
                        policy_ids_cited=outcome.policy_ids,
                        tool_calls=outcome.tool_calls,
                        grounding=outcome.grounding,
                        status="pending",
                        model=resp.model,
                    )
                    session.add(draft)
                    log_event(
                        session,
                        action="draft",
                        agent="drafter",
                        message_id=msg.message_id,
                        detail={"policies": outcome.policy_ids, "grounding_passed": outcome.grounding.get("passed")},
                    )
                    msg.status = "drafted"
                    counts["draft"] += 1

            session.commit()

    return counts


def _set_decision_human(session, message_id: str, reason: str, team: str) -> None:
    from sqlmodel import select

    row = session.exec(select(Decision).where(Decision.message_id == message_id)).first()
    if row:
        row.decision = "human"
        row.reason = reason
        row.rule_id = reason
        session.add(row)


def _apply_record_update(session, bookings, raw: dict, triage) -> None:
    rid = triage.fields.reservation_id
    if not rid:
        return
    res = bookings.get_reservation(reservation_id=rid)
    before = res.model_dump() if res else {}
    recognised = [a["kind"] for a in raw.get("attachments", []) if a.get("kind") in RECOGNISED_DOC_KINDS]
    if recognised:
        updates = {kind: "received_pending_review" for kind in recognised}
        bookings.update_documents(rid, **updates)
        detail = {"reservation_id": rid, "updates": updates, "before": {k: before.get(k) for k in updates}}
    else:
        bookings.record_guest_contact(rid, raw["received_at"])
        detail = {"reservation_id": rid, "last_guest_contact": raw["received_at"]}
    log_event(
        session, action="record_update", agent="rules", message_id=raw["message_id"], reservation_id=rid, detail=detail
    )


def _cost(resp) -> float:
    # Placeholder: fake/local provider is free. Real providers fill cost from pricing.yaml.
    return 0.0


def run_chaser_step() -> dict:
    with get_session() as session:
        bookings = SqliteBookings(session)
        reminders, skips = _run_chaser(session, bookings)
        for r in reminders:
            draft = Draft(
                reservation_id=r.reservation_id,
                kind="reminder",
                team="office",
                subject=f"Reminder: paperwork for {r.reservation_id}",
                text=r.text,
                policy_ids_cited=r.policy_ids,
                grounding=r.grounding,
                status="pending",
                tool_calls=[{"tool": "chaser", "args": {"missing": r.missing}, "result": {"arrival": r.arrival}}],
            )
            session.add(draft)
            log_event(
                session,
                action="chaser_reminder",
                agent="chaser",
                reservation_id=r.reservation_id,
                detail={"missing": r.missing},
            )
        for s in skips:
            log_event(
                session,
                action="chaser_skip",
                agent="chaser",
                reservation_id=s.reservation_id,
                detail={"reason": s.reason},
            )
        session.commit()
        return {"reminders": len(reminders), "skips": len(skips)}


def run_all() -> dict:
    inbox_counts = run_inbox()
    chaser_counts = run_chaser_step()
    return {"inbox": inbox_counts, "chaser": chaser_counts}
