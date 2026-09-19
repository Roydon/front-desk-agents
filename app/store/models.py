"""SQLModel tables. See docs/ARCHITECTURE.md Data model."""

from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class Unit(SQLModel, table=True):
    __tablename__ = "units"
    unit_id: str = Field(primary_key=True)
    unit_type: str
    max_length_ft: float | None = None
    max_beam_ft: float | None = None
    power: str | None = None
    notes: str | None = None


class Reservation(SQLModel, table=True):
    __tablename__ = "reservations"
    reservation_id: str = Field(primary_key=True)
    guest_name: str
    email: str | None = None
    phone: str | None = None
    unit_type: str
    unit_id: str | None = None
    arrival: str
    departure: str
    vessel_name: str | None = None
    length_ft: float | None = None
    beam_ft: float | None = None
    insurance_cert: str = "n/a"
    vessel_registration: str = "n/a"
    signed_contract: str = "n/a"
    deposit_paid: str = "n/a"
    last_guest_contact: str | None = None
    status: str = "confirmed"


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    message_id: str = Field(primary_key=True)
    channel: str
    received_at: str
    from_name: str | None = None
    from_phone: str | None = None
    from_email: str | None = None
    subject: str | None = None
    body: str
    body_redacted: str | None = None
    attachments: list = Field(default_factory=list, sa_column=Column(JSON))
    expected: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "new"


class TriageRow(SQLModel, table=True):
    __tablename__ = "triage_results"
    id: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(index=True)
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    model: str | None = None
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"
    id: int | None = Field(default=None, primary_key=True)
    message_id: str = Field(index=True)
    decision: str
    team: str | None = None
    reason: str | None = None
    rule_id: str | None = None


class Draft(SQLModel, table=True):
    __tablename__ = "drafts"
    draft_id: int | None = Field(default=None, primary_key=True)
    message_id: str | None = Field(default=None, index=True)
    reservation_id: str | None = None
    kind: str = "reply"  # reply | reminder
    team: str = "office"
    subject: str | None = None
    text: str = ""
    language: str = "en"
    policy_ids_cited: list = Field(default_factory=list, sa_column=Column(JSON))
    tool_calls: list = Field(default_factory=list, sa_column=Column(JSON))
    grounding: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"  # pending | approved | rejected | sent
    final_text: str | None = None
    edit_distance: float | None = None
    reviewed_at: str | None = None
    reject_reason: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    alert_id: int | None = Field(default=None, primary_key=True)
    message_id: str
    team: str
    callback: str | None = None
    summary: str
    created_at: str
    acknowledged_at: str | None = None


class Event(SQLModel, table=True):
    __tablename__ = "events"
    event_id: int | None = Field(default=None, primary_key=True)
    ts: str
    message_id: str | None = None
    reservation_id: str | None = None
    agent: str | None = None
    action: str
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
