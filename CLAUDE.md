# CLAUDE.md — front-desk-agents

A demo of AI agents for a marina & campground front desk: voicemail + email triage, grounded reply
drafts, a document chaser, an approval queue, safety alerts and an activity log. It is shown to a
prospective client (non-technical owner) in a 2-minute video and a live call. Clarity and
reliability matter more than features.

## Read first
1. `docs/REQUIREMENTS.md` — what to build (FR-/NFR- ids) and acceptance criteria
2. `docs/ARCHITECTURE.md` — layout, data model, interfaces
3. `docs/DEMO_SCRIPT.md` — the exact results the demo must produce
4. `docs/DECISIONS.md` — decisions already made; add an entry when you make a new one
5. `../TASKS.md` — the build plan; tick boxes as you finish

## Commands
| | |
|---|---|
| `make setup` | create venv with uv, install deps, copy `.env.example` → `.env` if missing |
| `make seed` | reset SQLite and load `data/` |
| `make demo` | reset → seed → process inbox → run chaser → print summary → serve on :8000 |
| `make serve` | run the web app only |
| `make test` | pytest (uses `FakeProvider`, no network) |
| `make eval` | run triage over the 35 labelled messages with the configured provider |
| `make lint` | ruff check + ruff format --check |
| `make reset` | delete `var/` (db, outbox, logs) |

## Non-negotiable rules
- **Nothing is sent automatically.** Every guest-facing message is a draft in the approval queue.
  "Sending" writes a file to `var/outbox/`. There is no real email/SMS client in this repo.
- **Safety first, in code.** Safety keyword + intent rules run before and after the model and
  produce an alert, never a draft. Do not move this logic into a prompt.
- **Facts come from tools.** Availability, prices, dates, unit ids and policies must come from
  `check_availability`, `get_policy`, `get_reservation`. The grounding check rejects drafts that
  mention a `$` amount, date or unit id not present in tool results.
- **No card data.** Detect and redact card numbers before any model call; never echo them.
- **Payments are links only** (`payment_link` tool → Stripe-style stub URL). Agents never quote a
  balance they didn't get from `get_reservation`, never process refunds, never promise exceptions.
- **Fixed clock.** Use `app/clock.py` (`DEMO_TODAY=2026-08-24`, America/New_York). Never call
  `datetime.now()` directly.
- **Deterministic.** temperature 0; seedable; the demo must give the same routing every run.
- **Fixtures are frozen.** Do not edit `data/` or `config/` to make a test pass — fix the code.
  You may add new files.
- **Fictional data only.** No real names, phone numbers or businesses.

## Conventions
- Python 3.11, type hints everywhere, Pydantic v2 models at every boundary (LLM output, tool I/O).
- Connectors are `typing.Protocol` interfaces with a demo implementation; keep production shapes
  (see ARCHITECTURE.md §Connectors) so real Gmail/Twilio/Stripe/booking adapters can drop in.
- Prompts live in `app/prompts/*.md`, not inline strings. Log prompt name + version with each call.
- Every agent step writes an `events` row (see ARCHITECTURE.md). If it isn't in the log, it didn't happen.
- UI: server-rendered Jinja2 + a little vanilla JS. Plain, readable, works at 1280×720 for recording.
- Small commits per milestone: `M<n>: <name>`.

## Definition of done
`make lint test` green · `make eval` meets the thresholds in REQUIREMENTS.md FR-10 · every line of
DEMO_SCRIPT.md §Expected results holds after `make reset demo` · README quickstart works on a
fresh clone.

## When unsure
Ask. Don't widen scope (no live phone answering, no real integrations, no auth system) — those are
listed as out of scope on purpose.
