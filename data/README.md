# Fixtures — frozen

Fictional data for Lakeside Cove Marina & Campground. The demo and the eval depend on these exact
values; change code, not fixtures. Demo date: Monday 2026-08-24, 08:00 America/New_York.

| file | contents |
|---|---|
| `units.csv` | 40 units: D1–D8 transient slips (30/40/50 ft classes), S01–S12 seasonal slips, RV1–RV10 full hookup (≤ 40 ft, 50A), RV11–RV14 water + electric (≤ 32 ft, 30A), T1–T6 tent |
| `reservations.csv` | 22 reservations. Document columns: `ok` · `missing` · `n/a` (runtime also uses `received_pending_review`) |
| `messages.jsonl` | 35 messages (VM01–VM15 voicemail transcripts, EM01–EM20 emails), each with an `expected` label block used by `make eval` and the demo checks |
| `audio/` | optional `<id>.wav` voicemail recordings; if present they are transcribed instead of using `body` |

`expected` fields: `intent`, `team`, `decision`, `urgency`, `reason` (rule id for `human`/`alert`/`ignore`),
`fields` (exact-match targets), optional `alt_intents` / `alt_reasons` (also accepted), `notes`
(what a correct draft contains — used by humans and by DEMO_SCRIPT.md, not scored automatically).

Verified on 2026-09-19: safety keywords trip exactly VM02, VM03, VM12; card detection only EM11;
injection patterns only EM17; availability and chaser outcomes match DEMO_SCRIPT.md.
