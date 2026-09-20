"""Privacy hardening for the hosted demo."""

from fastapi.testclient import TestClient

from app.main import app


def test_no_public_api_docs_and_noindex():
    c = TestClient(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404
    r = c.get("/robots.txt")
    assert r.status_code == 200 and "Disallow: /" in r.text
    assert r.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_card_number_not_stored_raw():
    from sqlmodel import select

    from app.pipeline import run_all
    from app.store.db import get_session
    from app.store.models import Message
    from scripts.seed import seed

    seed()
    run_all()
    with get_session() as s:
        m = s.exec(select(Message).where(Message.message_id == "EM11")).one()
        assert "4111" not in (m.body or "") and "4111" not in (m.body_redacted or "")
        assert "[card removed]" in m.body
