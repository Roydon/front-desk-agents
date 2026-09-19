# Lakeside Cove front-desk agents (demo)

An AI front desk for a marina & campground: it triages weekend voicemails and emails, drafts
grounded replies, chases missing paperwork, sends safety calls straight to a person, and logs
every step - with a human approving every guest-facing message.

> Fictional business and data. Nothing is ever sent to a guest without a human clicking Approve.

## 60-second quickstart

```bash
cd repo
make setup      # uv venv + deps + .env
make demo       # reset -> seed -> triage inbox -> chaser -> summary -> serve on :8000
```

Open http://localhost:8000. You should see: **15 drafted, 14 need a person, 3 safety alerts,
2 records updated, 1 ignored**, plus **4 chaser reminders** and **19 pending approvals**.

Other targets: `make test` (pytest, no network) · `make eval` (metrics over the 35 labelled
messages) · `make lint` · `make reset`.

## How it works

```
inbox -> guards (safety / card redaction / injection) -> triage (LLM) -> rules.decide()
      -> [alert | needs a person | draft | record update | ignore]
draft -> tools (availability, quote, policy, reservation, payment_link) -> grounding check
      -> approval queue -> approve/edit/reject -> var/outbox/
chaser (14/7/2-day offsets) -> reminders for missing docs
every step -> events table -> /log
```

Guarantees built into code (not prompts):
- **Nothing auto-sends.** Every guest message is a draft; "send" writes a file to `var/outbox/`.
- **Safety first.** Keyword + intent rules raise an alert, never a draft.
- **Grounded facts.** Every `$`, date and unit id in a draft must come from a tool result.
- **No card data.** Card numbers are detected and redacted before any model call.
- **Deterministic.** Fixed clock (2026-08-24), temperature 0; the same routing every run.

## Models

Pluggable provider layer. The offline demo runs on `FakeProvider` (recorded triage) - deterministic
and free. Set `LLM_PROVIDER=openrouter` with `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` to run a live
model for triage; the drafter composes grounded replies from tool results either way.

## What it will NOT do (out of scope for the MVP)

Answer live phone calls · send real email/SMS · integrate a real booking or payment system · take
payments or process refunds · auto-send anything · user accounts. See `docs/REQUIREMENTS.md`.

## Deploy (Fly.io)

Containerised; boots to a fresh demo state on every start (ephemeral disk). Protected by HTTP Basic
Auth (`APP_USER` / `APP_PASSWORD` secrets). `/reset` re-seeds on demand. See `fly.toml`.
