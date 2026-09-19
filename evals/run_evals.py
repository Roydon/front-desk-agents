"""Run triage + rules over the 35 labelled messages and print metrics (FR-10)."""

from __future__ import annotations

import json

from app.agents import drafter
from app.agents.triage import run_triage
from app.clock import now
from app.connectors.bookings import SqliteBookings
from app.connectors.inbox import JsonlInbox
from app.guards import run_guards
from app.llm.factory import get_provider
from app.rules import decide
from app.settings import settings
from app.store.db import get_session
from scripts.seed import seed

FIELD_KEYS = ["arrival", "departure", "boat_length_ft", "reservation_id"]


def predict(raw, guards, triage, bookings) -> tuple[str, str | None]:
    d = decide(raw, guards, triage, bookings)
    if d.decision == "draft":
        outcome = drafter.compose(raw, triage, bookings)
        if outcome.kind == "defer":
            return "human", outcome.defer_reason
    return d.decision, d.reason


def run() -> dict:
    seed()
    provider = get_provider()
    rows = JsonlInbox().fetch_new()

    n = len(rows)
    intent_ok = team_ok = decision_ok = 0
    safety_total = safety_hit = 0
    false_alerts = 0
    field_total = field_ok = 0
    misses = []

    with get_session() as session:
        bookings = SqliteBookings(session)
        for raw in rows:
            exp = raw["expected"]
            guards = run_guards(raw.get("body") or "")
            triage, _, fail = run_triage(provider, raw)
            if fail:
                pred_decision, pred_intent, pred_team = "human", "other", "office"
            else:
                pred_decision, _ = predict(raw, guards, triage, bookings)
                pred_intent, pred_team = triage.intent, triage.team

            if pred_intent == exp["intent"]:
                intent_ok += 1
            if pred_team == exp.get("team"):
                team_ok += 1
            if pred_decision == exp["decision"]:
                decision_ok += 1
            else:
                misses.append({"id": raw["message_id"], "expected": exp["decision"], "got": pred_decision})

            if exp["decision"] == "alert":
                safety_total += 1
                if pred_decision == "alert":
                    safety_hit += 1
            elif pred_decision == "alert":
                false_alerts += 1

            for k in FIELD_KEYS:
                if k in exp.get("fields", {}):
                    field_total += 1
                    got = getattr(triage.fields, k, None) if not fail else None
                    if str(got) == str(exp["fields"][k]):
                        field_ok += 1

    metrics = {
        "provider": settings.llm_provider,
        "n": n,
        "intent_accuracy": round(intent_ok / n, 3),
        "team_accuracy": round(team_ok / n, 3),
        "decision_accuracy": round(decision_ok / n, 3),
        "safety_recall": round(safety_hit / safety_total, 3) if safety_total else 1.0,
        "false_alerts": false_alerts,
        "field_exact_match": round(field_ok / field_total, 3) if field_total else 1.0,
        "misses": misses,
    }
    return metrics


def main() -> None:
    m = run()
    print("\n=== Eval metrics ({} over {} messages) ===".format(m["provider"], m["n"]))
    for k in [
        "intent_accuracy",
        "team_accuracy",
        "decision_accuracy",
        "safety_recall",
        "false_alerts",
        "field_exact_match",
    ]:
        print(f"  {k:20s}: {m[k]}")
    if m["misses"]:
        print("  misses:", m["misses"])

    out_dir = settings.var_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = now().strftime("%Y%m%dT%H%M%S")
    (out_dir / f"{ts}.json").write_text(json.dumps(m, indent=2))
    print(f"  written: var/eval/{ts}.json\n")

    thresholds = {
        "safety_recall": (m["safety_recall"] >= 1.0),
        "false_alerts": (m["false_alerts"] <= 1),
        "decision_accuracy": (m["decision_accuracy"] >= 0.90),
        "intent_accuracy": (m["intent_accuracy"] >= 0.85),
        "field_exact_match": (m["field_exact_match"] >= 0.80),
    }
    failed = [k for k, ok in thresholds.items() if not ok]
    print("  thresholds:", "PASS" if not failed else f"FAIL {failed}")


if __name__ == "__main__":
    main()
