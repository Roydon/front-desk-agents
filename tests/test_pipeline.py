"""Tests run against the deterministic FakeProvider (no network)."""

from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("LLM_PROVIDER", "fake")

from app.connectors.bookings import _overlaps  # noqa: E402
from app.guards import redact_card, safety_hits  # noqa: E402
from evals.run_evals import run  # noqa: E402


def test_departure_day_is_free():
    # A stay ending on the day another begins does not overlap.
    assert _overlaps("2026-08-28", "2026-08-30", "2026-08-26", "2026-08-28") is False
    assert _overlaps("2026-08-28", "2026-08-30", "2026-08-26", "2026-08-29") is True


def test_card_redaction_luhn():
    out, found = redact_card("My card is 4111 1111 1111 1111 exp 09/28 CVV 123")
    assert found is True
    assert "4111" not in out and "[card removed]" in out


def test_non_card_number_not_redacted():
    out, found = redact_card("Our boat is 38 feet, beam 13, arriving the 4th")
    assert found is False


def test_safety_keywords_fire_on_hazards_only():
    assert safety_hits("the boat is taking on water at the stern")
    assert not safety_hits("what time does the fuel dock open on Sunday")


def test_eval_thresholds():
    m = run()
    assert m["decision_accuracy"] == 1.0
    assert m["safety_recall"] == 1.0
    assert m["false_alerts"] <= 1
    assert m["intent_accuracy"] >= 0.85
    assert m["field_exact_match"] >= 0.80


def test_labour_day_is_a_holiday():
    from app.tools.pricing import is_holiday

    assert is_holiday(date(2026, 9, 4)) == "Labour Day"
    assert is_holiday(date(2026, 8, 28)) is None
