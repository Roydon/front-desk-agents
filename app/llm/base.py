"""LLM provider protocol and boundary models."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Intent = Literal[
    "new_booking",
    "change_or_cancel",
    "payment",
    "documents",
    "boatyard_service",
    "general_question",
    "complaint_or_dispute",
    "safety_urgent",
    "other",
]
Urgency = Literal["immediate", "today", "routine"]
Team = Literal["office", "dockmaster", "boatyard"]


class TriageFields(BaseModel):
    guest_name: str | None = None
    phone: str | None = None
    email: str | None = None
    reservation_id: str | None = None
    unit_type: str | None = None
    arrival: str | None = None
    departure: str | None = None
    boat_length_ft: float | None = None
    beam_ft: float | None = None
    rv_length_ft: float | None = None
    party_size: int | None = None
    pets: int | None = None
    units_requested: int | None = None
    language: str | None = None


class TriageResult(BaseModel):
    intent: Intent
    urgency: Urgency = "routine"
    team: Team = "office"
    fields: TriageFields = Field(default_factory=TriageFields)
    summary: str = ""
    confidence: float = 1.0
    spam: bool = False


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class LLMProvider(Protocol):
    name: str

    def triage(self, message: dict) -> tuple[TriageResult, LLMResponse]:
        """Return a validated TriageResult plus usage metadata."""
        ...
