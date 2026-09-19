"""reset -> seed -> run inbox -> run chaser -> print summary -> serve."""

from __future__ import annotations

import subprocess
import sys

from app.pipeline import run_all
from scripts.cost_report import main as write_cost_report
from scripts.seed import seed


def summarise() -> None:
    c = seed()
    result = run_all()
    write_cost_report()
    inbox, chaser = result["inbox"], result["chaser"]
    print("\n=== Monday morning at Lakeside Cove ===")
    print(f"Messages in: {inbox['in']} ({c['messages']} seeded)")
    print(
        f"Decisions: {inbox['draft']} drafted | {inbox['human']} need a person | "
        f"{inbox['alert']} safety alerts | {inbox['record_update']} records updated | "
        f"{inbox['ignore']} ignored"
    )
    print(f"Chaser: {chaser['reminders']} reminders drafted | {chaser['skips']} skipped")
    print(f"Approval queue: {inbox['draft'] + chaser['reminders']} pending")
    print("=======================================\n")


def main(serve: bool = True) -> None:
    summarise()
    if serve:
        print("Starting the web app on http://localhost:8000 (Ctrl-C to stop)...")
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main(serve="--no-serve" not in sys.argv)
