# Decisions

Add an entry for every decision that changes structure, dependencies or behaviour.

## D-001 Safety and escalation rules live in code, not prompts
Rules must be testable, deterministic and explainable to a non-technical owner. The model
classifies; code decides. Keyword safety checks run before the model so a model failure can't hide an emergency.

## D-002 Local-first model, cloud optional
Ollama (`llama3.1:8b`) by default so the demo runs offline and free; Anthropic behind a switch
(Haiku for triage, Sonnet for drafts) to show the production path and its cost.

## D-003 Tools are the source of truth + a grounding check
The drafter may only state prices, dates and units that a tool returned. A post-check enforces it
instead of trusting the prompt.

## D-004 Mock connectors with production-shaped interfaces
The client hasn't named their systems. Protocols mirror Gmail/IMAP, Twilio/RingCentral voicemail,
their booking platform, SMTP/SMS and Stripe Payment Links, so real adapters replace the mocks
without touching agents.

## D-005 Fixed clock
Demo date 2026-08-24 so chaser offsets (T-14/7/2) and "this Friday" resolve the same every run.

## D-006 SQLite + server-rendered UI
Fewest moving parts for a small team; readable when screen-recorded; no build step.

## D-007 Human approval for every outbound message
Autonomy is raised later per message type, based on measured edit distance - not assumed.

## D-008 OpenRouter provider for the hosted demo (portable JSON, not native tools)
Added `OpenRouterProvider` (OpenAI-compatible) so the hosted demo can run a cheap, reliable model
on the client's key without an Anthropic bill. Triage uses a single-JSON contract and the drafter
composes from tool results, so the pinned model stays swappable. Pinned model for the live demo:
`google/gemini-3.8-flash`.

## D-009 Deterministic FakeProvider is the source of truth; live model is verified against it
`FakeProvider` replays the labelled triage, so `make demo`/tests/eval are deterministic and free.
The live model is graded against the same 35-message eval before it ships. Recorded metrics:
- **FakeProvider:** decision 1.00, safety recall 1.00, false alerts 0, intent 1.00, field 0.85.
- **OpenRouter (gemini-3.8-flash):** decision 1.00, safety recall 1.00, false alerts 0,
  intent 0.94, field 0.82. Guards (safety, card redaction, injection) are deterministic and
  identical under both providers.

## D-010 Response cache, baked into the deploy image
LLM responses are cached on disk keyed by (provider, model, prompt, input) so eval re-runs and a
rehearsed demo survive free-tier limits and outages. The cache of real model responses is baked
into the Docker image so cold starts stay fast and reproducible. Swapping `OPENROUTER_MODEL`
requires regenerating the cache before redeploy.

## D-011 Hosted on Fly.io: ephemeral, seed-on-boot, HTTP Basic Auth
Containerised; the disk is ephemeral and every boot re-seeds to a known-good state matching
DEMO_SCRIPT (no volume). A shared-password HTTP Basic Auth gate (Fly secrets) protects the public
URL and auto-disables locally so tests/eval are unaffected. `/reset` re-seeds on demand.

## D-012 Seasonal-slip enquiries: dedicated quote path, routed to the dockmaster
A seasonal-slip pricing question is answered by a shared `_seasonal()` composer (per-foot season
rate + 25% deposit, cites P2/P3) whether a model labels it a booking or a general question; the
draft routes to the dockmaster. Refusal checks (liveaboards, events -> `no_policy`) run first so a
unit-type tag can't override them.
