"""FastAPI app + routes (FR-7, FR-8, FR-9)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from rapidfuzz.distance import Levenshtein
from sqlmodel import select

from app.auth import require_auth
from app.clock import now
from app.connectors.outbound import FileOutbound
from app.store.db import get_session, log_event
from app.store.models import Alert, Decision, Draft, Event, Message, TriageRow

WEB = Path(__file__).resolve().parent / "web"
templates = Jinja2Templates(directory=str(WEB / "templates"))
app = FastAPI(title="Lakeside Cove front desk")
app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")

REASON_LABELS = {
    "complaint_or_dispute": "Complaint or dispute",
    "cancel_or_refund": "Cancellation / refund",
    "seasonal_tenant": "Seasonal tenant",
    "low_confidence": "Low confidence (unclear message)",
    "no_policy": "No matching policy",
    "group_booking": "Group booking (over 3 units)",
    "vendor_other": "Vendor / other",
    "urgent_service": "Urgent boatyard service",
    "card_data": "Card number (redacted)",
    "payment": "Payment / receipt",
    "suspicious_instructions": "Suspicious instructions",
    "legal_threat": "Legal threat",
    "triage_failed": "Triage failed",
    "ungrounded": "Draft failed grounding",
}


def _active_alerts(session) -> list[Alert]:
    return session.exec(select(Alert).where(Alert.acknowledged_at.is_(None))).all()


def _ctx(request: Request, session, **kw) -> dict:
    return {"request": request, "active_alerts": _active_alerts(session), "now": now(), **kw}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def home(request: Request, _=Depends(require_auth)):
    with get_session() as session:
        msgs = session.exec(select(Message)).all()
        decisions = {d.message_id: d for d in session.exec(select(Decision)).all()}
        drafts = session.exec(select(Draft).where(Draft.status == "pending")).all()
        by_decision: dict[str, int] = {}
        for d in decisions.values():
            by_decision[d.decision] = by_decision.get(d.decision, 0) + 1
        reminders = [d for d in drafts if d.kind == "reminder"]
        vm = sum(1 for m in msgs if m.channel == "voicemail")
        em = sum(1 for m in msgs if m.channel == "email")
        summary = {
            "total": len(msgs),
            "voicemail": vm,
            "email": em,
            "drafted": by_decision.get("draft", 0),
            "human": by_decision.get("human", 0),
            "alert": by_decision.get("alert", 0),
            "record_update": by_decision.get("record_update", 0),
            "ignore": by_decision.get("ignore", 0),
            "reminders": len(reminders),
            "pending": len(drafts),
        }
        return templates.TemplateResponse(request, "index.html", _ctx(request, session, summary=summary))


@app.get("/queue")
def queue(request: Request, _=Depends(require_auth)):
    with get_session() as session:
        drafts = session.exec(select(Draft).where(Draft.status == "pending").order_by(Draft.draft_id.desc())).all()
        triage = {t.message_id: t for t in session.exec(select(TriageRow)).all()}
        groups: dict[str, list] = {}
        for d in drafts:
            summ = triage[d.message_id].result.get("summary") if d.message_id in triage else None
            groups.setdefault(d.team, []).append({"draft": d, "summary": summ})
        return templates.TemplateResponse(request, "queue.html", _ctx(request, session, groups=groups))


@app.get("/queue/{draft_id}")
def draft_detail(draft_id: int, request: Request, _=Depends(require_auth)):
    with get_session() as session:
        d = session.get(Draft, draft_id)
        msg = session.get(Message, d.message_id) if d.message_id else None
        triage = None
        if d.message_id:
            triage = session.exec(select(TriageRow).where(TriageRow.message_id == d.message_id)).first()
        return templates.TemplateResponse(request, "draft.html", _ctx(request, session, d=d, msg=msg, triage=triage))


@app.post("/queue/{draft_id}/approve")
def approve(draft_id: int, final_text: str = Form(...), _=Depends(require_auth)):
    with get_session() as session:
        d = session.get(Draft, draft_id)
        original = d.text
        edited = final_text.strip() != original.strip()
        dist = Levenshtein.normalized_distance(original, final_text) if edited else 0.0
        d.final_text = final_text
        d.edit_distance = round(dist, 3)
        d.status = "approved"
        d.reviewed_at = now().isoformat()
        to = None
        msg = session.get(Message, d.message_id) if d.message_id else None
        if msg:
            to = msg.from_email or msg.from_phone
        channel = "email" if (to and "@" in to) else "sms"
        path = FileOutbound().send(
            draft_id=draft_id,
            to=to or "guest",
            channel=channel,
            subject=d.subject or "",
            text=final_text,
        )
        d.status = "sent"
        session.add(d)
        log_event(
            session,
            action="approve",
            agent="staff",
            message_id=d.message_id,
            reservation_id=d.reservation_id,
            detail={"edit_distance": d.edit_distance, "edited": edited},
        )
        log_event(
            session,
            action="send",
            agent="outbound",
            message_id=d.message_id,
            detail={"outbox": path, "channel": channel},
        )
        session.commit()
    return RedirectResponse("/queue", status_code=303)


@app.post("/queue/{draft_id}/reject")
def reject(draft_id: int, reason: str = Form(...), _=Depends(require_auth)):
    with get_session() as session:
        d = session.get(Draft, draft_id)
        d.status = "rejected"
        d.reject_reason = reason
        d.reviewed_at = now().isoformat()
        session.add(d)
        log_event(session, action="reject", agent="staff", message_id=d.message_id, detail={"reason": reason})
        session.commit()
    return RedirectResponse("/queue", status_code=303)


@app.get("/needs-person")
def needs_person(request: Request, _=Depends(require_auth)):
    with get_session() as session:
        rows = session.exec(select(Decision).where(Decision.decision == "human")).all()
        msgs = {m.message_id: m for m in session.exec(select(Message)).all()}
        items = []
        for d in rows:
            m = msgs.get(d.message_id)
            items.append(
                {
                    "id": d.message_id,
                    "reason": d.reason,
                    "reason_label": REASON_LABELS.get(d.reason, d.reason),
                    "team": d.team,
                    "subject": (m.subject if m else None) or (m.from_name if m else ""),
                    "body": (m.body_redacted or m.body) if m else "",
                }
            )
        return templates.TemplateResponse(request, "needs_person.html", _ctx(request, session, items=items))


@app.get("/alerts")
def alerts_page(request: Request, _=Depends(require_auth)):
    with get_session() as session:
        rows = session.exec(select(Alert).order_by(Alert.alert_id.desc())).all()
        msgs = {m.message_id: m for m in session.exec(select(Message)).all()}
        items = [{"alert": a, "msg": msgs.get(a.message_id)} for a in rows]
        return templates.TemplateResponse(request, "alerts.html", _ctx(request, session, items=items))


@app.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, _=Depends(require_auth)):
    with get_session() as session:
        a = session.get(Alert, alert_id)
        a.acknowledged_at = now().isoformat()
        session.add(a)
        log_event(session, action="acknowledge", agent="staff", message_id=a.message_id, detail={"alert_id": alert_id})
        session.commit()
    return RedirectResponse("/alerts", status_code=303)


@app.get("/log")
def log_page(request: Request, _=Depends(require_auth)):
    with get_session() as session:
        events = session.exec(select(Event).order_by(Event.event_id.desc())).all()
        drafts = session.exec(select(Draft)).all()
        approved = [d for d in drafts if d.edit_distance is not None]
        avg_edit = round(sum(d.edit_distance for d in approved) / len(approved), 3) if approved else 0.0
        totals = {
            "events": len(events),
            "input_tokens": sum(e.input_tokens for e in events),
            "output_tokens": sum(e.output_tokens for e in events),
            "cost_usd": round(sum(e.cost_usd for e in events), 4),
            "pending": sum(1 for d in drafts if d.status == "pending"),
            "avg_edit": avg_edit,
        }
        return templates.TemplateResponse(
            request, "log.html", _ctx(request, session, events=events[:200], totals=totals)
        )


@app.post("/reset")
def reset(_=Depends(require_auth)):
    from app.pipeline import run_all
    from scripts.seed import seed

    seed()
    run_all()
    return RedirectResponse("/", status_code=303)
