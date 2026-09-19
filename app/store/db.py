"""Engine / session / reset helpers."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.clock import now
from app.settings import settings
from app.store import models  # noqa: F401  (register tables)
from app.store.models import Event

settings.var_dir.mkdir(parents=True, exist_ok=True)
_engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)


def engine():
    return _engine


def get_session() -> Session:
    return Session(_engine)


def reset_db() -> None:
    """Drop and recreate all tables."""
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.drop_all(_engine)
    SQLModel.metadata.create_all(_engine)


def create_all() -> None:
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(_engine)


def log_event(
    session: Session,
    *,
    action: str,
    agent: str | None = None,
    message_id: str | None = None,
    reservation_id: str | None = None,
    detail: dict | None = None,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
) -> None:
    """Append a row to events. If it isn't in the log, it didn't happen."""
    session.add(
        Event(
            ts=now().isoformat(),
            action=action,
            agent=agent,
            message_id=message_id,
            reservation_id=reservation_id,
            detail=detail or {},
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )
