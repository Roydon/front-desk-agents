# Requirements — front-desk-agents MVP

Fictional business: **Lakeside Cove Marina & Campground** (placeholder — swap policies for the
client's before the call). Demo date **Monday 2026-08-24**, America/New_York. Labour Day weekend
is **Fri 2026-09-04 → Mon 2026-09-07**.

## Scope

In: voicemail + email intake, triage, rule-based routing and escalation, grounded reply drafts,
document chaser, record updates from guest messages, approval queue, safety alerts, activity log,
labelled evaluation, cost estimate.

Out (say so in the README): answering live calls, real email/SMS/voice/booking/payment
integrations, taking payments or processing refunds, auto-sending, user accounts/auth,
multi-property support, production deployment.

## Glossary
- **Message** — one voicemail transcript or one email (`data/messages.jsonl`).
- **Decision** — what happens to a message: `alert` · `human` · `draft` · `record_update` · `ignore`.
- **Team** — `office` · `dockmaster` · `boatyard`.
- **Unit types** — `transient_slip` · `seasonal_slip` · `campsite_rv_full` · `campsite_rv_we` · `campsite_tent`.

---

## Functional requirements

### FR-1 Intake
- Load messages through `InboxConnector` from `data/messages.jsonl`, processed in `received_at` order.
- Voicemails arrive as transcripts. If `data/audio/<id>.wav` exists, transcribe it with
  faster-whisper (`base.en`) and use that text instead (optional; the demo works without audio).
- Emails have `subject`, `body`, `attachments` (filenames + `kind`, e.g. `insurance_cert`).
- Store every message with status `new`.

**Accept:** `make seed` stores 35 messages (15 voicemail, 20 email).

### FR-2 Triage
Model output validated as `TriageResult`:

| field | type |
|---|---|
| `intent` | `new_booking` · `change_or_cancel` · `payment` · `documents` · `boatyard_service` · `general_question` · `complaint_or_dispute` · `safety_urgent` · `other` |
| `urgency` | `immediate` · `today` · `routine` |
| `team` | `office` · `dockmaster` · `boatyard` |
| `fields` | `guest_name`, `phone`, `email`, `reservation_id`, `unit_type`, `arrival`, `departure`, `boat_length_ft`, `beam_ft`, `rv_length_ft`, `party_size`, `pets`, `units_requested`, `language` (all optional) |
| `summary` | ≤ 25 words, plain English, for staff |
| `confidence` | 0–1 |

- Invalid JSON → one retry with the validation error appended → still invalid → decision `human`, reason `triage_failed`.
- Dates resolved against the fixed clock ("this Friday" on 2026-08-24 = 2026-08-28).

### FR-3 Guards and rules (deterministic, in code)
Run in this order; first match wins. Config: `config/escalation.yaml`, `config/routing.yaml`.

1. **Pre-model safety keywords** in the raw text (case-insensitive, whole word/phrase) → `alert`
   (model still runs, for the summary). No non-safety message in `data/` may trip a keyword.
2. **Card number** (13–19 digits, Luhn-valid, spaces/dashes allowed) → redact to `[card removed]`,
   plus any expiry (`exp 09/28`) and CVV/CVC (`CVV 123`) next to it, in stored text *and* model
   input → `human`, reason `card_data`.
3. **Prompt-injection patterns** → `human`, reason `suspicious_instructions`; the model never sees
   tool access for this message.
4. After the model: `intent == safety_urgent` → `alert`.
5. Escalation rules from `escalation.yaml` (dispute, refund/cancel, legal threat, seasonal tenant,
   group > 3 units, vendor/other, low confidence < 0.70) → `human` with the rule id as reason.
6. `documents` intent with a recognised attachment, or a reply from a guest with a reservation
   whose only need is acknowledgement → `record_update`.
7. Spam/robocall (`other` + `spam: true` in model output) → `ignore` (logged, not shown in queue).
8. Otherwise → `draft`, team from `routing.yaml`.

**Accept:** decisions for all 35 messages match `expected.decision` in `data/messages.jsonl`
(with `FakeProvider` returning the labelled triage). Safety recall 3/3.

### FR-4 Reply drafter
Tools (Pydantic in/out):

| tool | returns |
|---|---|
| `check_availability(unit_type, arrival, departure, boat_length_ft?, beam_ft?, rv_length_ft?)` | `available` (all fitting free units), `recommended` (available units in the smallest size class that fits), and a reason for each excluded unit |
| `quote(item, nights?, length_ft?, arrival?)` | `item` = a unit type or `haul_out` · `launch_ramp` · `trailer_parking`; returns nightly/unit rate, total, deposit and any holiday minimum — **the `$` amounts the draft may use** (policy text from `get_policy` also counts) |
| `get_policy(topic or id)` | policy sections (id + text) from `config/policies.md` |
| `get_reservation(id or email or phone)` | reservation incl. document status |
| `payment_link(reservation_id)` | stub URL `https://pay.example.test/lakeside/<id>` |

- Reply in the guest's language (EM16 is Spanish). Sign as "Lakeside Cove front desk".
- Must not promise a booking — say what is available and how to confirm (deposit link or call).
- **Grounding check** after drafting: every `$` amount, calendar date and unit id in the draft must
  appear in this message's tool results or triage fields. Fail → `human`, reason `ungrounded`,
  keep the failed draft attached for staff to see.
- No applicable policy found for the question → `human`, reason `no_policy` (EM04, EM12).
- Stored draft includes `policy_ids_cited`, `tool_calls`, model, tokens, latency.

**Accept (VM01):** draft says two slips fit a 38-ft boat for Sep 4–7, quotes **$133.00/night**,
**3-night holiday minimum ($399.00)**, deposit **$133.00**, and the 30-day holiday cancellation
terms; cites **P2, P3, P4, P5**; `check_availability` returned available **D6, D8**, recommended **D6**.

### FR-5 Document chaser
Config `config/chaser.yaml`. Runs after the inbox is processed.

- For each reservation arriving exactly **14, 7 or 2 days** after today, list missing required
  items for its unit type (`insurance_cert`, `vessel_registration`, `signed_contract`, `deposit_paid`).
- Items with status `ok` or `received_pending_review` count as received.
- Skip (and log the reason) if: every item that was missing was received within the last 48 h →
  `document_received` · guest contacted us within **48 hours** → `guest_contacted` · a reminder
  already exists for this reservation today → `already_reminded`. Unit types with no required
  items (seasonal) and reservations with nothing missing are not considered at all.
- Draft one reminder per reservation naming **only** the missing items, the arrival date, and a
  `payment_link` when the deposit is missing. Drafts go to the approval queue, team `office`.
- Log every skip with its reason.

**Accept:** 4 reminders — **R-1046** (vessel registration, T-2), **R-1048** (insurance, T-7),
**R-1050** (deposit, T-7), **R-1055** (contract + deposit, T-14). 2 skips — **R-1047**
(`document_received`, from EM01), **R-1052** (`guest_contacted`, from EM02). **R-1049** and
**R-1054** have missing items but are not on an offset day → no reminder, no skip entry.

### FR-6 Record updates
- EM01 (insurance certificate attached, R-1047) → set `insurance_cert = received_pending_review`.
- EM02 (guest will sign tonight, R-1052) → set `last_guest_contact` to the message time.
- VM13 (R-1047 asks whether insurance arrived) → draft confirms it was received and is being reviewed.
- Every update writes an `events` row with before/after values.

### FR-7 Approval queue
- `/queue` lists pending drafts, newest first, grouped by team, with the triage summary.
- `/queue/{id}` shows the original message, triage result, tools called with results, policies
  cited, grounding status, and the draft in an editable textarea.
- Actions: **Approve** · **Edit & approve** · **Reject** (reason required). Record
  `edit_distance` (character Levenshtein, normalised 0–1) on approve.
- Sending uses `OutboundConnector` → writes `var/outbox/<draft_id>.txt` with headers.
- Messages decided `human` appear in a separate "Needs a person" list with the reason.

### FR-8 Safety alerts
- `alert` decisions create an `Alert` (message, transcript, callback number, team, time) sent via
  `AlertConnector` → console + `var/outbox/alerts/`.
- Red banner on every page until a staff member clicks Acknowledge (logged).
- **No draft is created** for an alert message.

**Accept:** VM02 (boat taking on water), VM03 (fuel smell at fuel dock), VM12 (fall from dock,
bleeding) raise alerts to `dockmaster`; no other message does.

### FR-9 Activity log
- `events` row for every step: intake, guard hit, triage, rule, tool call, draft, grounding
  check, chaser run/skip, record update, approve/edit/reject, send, alert, acknowledge.
- `/log` shows today's counts (in, drafted, needs a person, alerts, ignored), pending approvals,
  average edit distance, total tokens and **cost in USD**, and a filterable event table.

### FR-10 Evaluation
- `make eval` runs triage + rules over all 35 messages with the configured provider and prints:
  intent accuracy, team accuracy, decision accuracy, safety recall, false-alert count, and field
  exact-match rate (arrival, departure, boat_length_ft, reservation_id where labelled).
- Writes `var/eval/<timestamp>.json`.
- **Thresholds (Ollama `llama3.1:8b`):** safety recall = 1.0 · false alerts ≤ 1 · decision
  accuracy ≥ 0.90 · intent accuracy ≥ 0.85 · field exact-match ≥ 0.80. Anthropic Haiku should
  exceed all of these; record both in `docs/DECISIONS.md`.
- CI runs the same harness with `FakeProvider` to test the rules and scoring, not the model.

### FR-11 Cost estimate
`make demo` writes `docs/COST.md`: tokens per message type from the log × `config/pricing.yaml`,
projected per month at **100 / 500 / 2,000 messages per day**, for Haiku-triage + Sonnet-draft and
for Haiku-only, with a note that summer peak volume drives the bill.

---

## Non-functional requirements
- **NFR-1 Local first:** default provider Ollama (`llama3.1:8b`, alt `qwen2.5:7b`); the whole demo runs offline.
- **NFR-2 Switchable:** `LLM_PROVIDER=anthropic` uses `ANTHROPIC_TRIAGE_MODEL` (Haiku) and `ANTHROPIC_DRAFT_MODEL` (Sonnet).
- **NFR-3 Deterministic:** temperature 0; same routing on every run.
- **NFR-4 Fixed clock:** `DEMO_TODAY=2026-08-24` 08:00 America/New_York via `app/clock.py`.
- **NFR-5 Speed:** `make demo` finishes processing in < 3 minutes on an Apple-silicon Mac with Ollama.
- **NFR-6 Privacy:** fictional data only; `.env` for secrets; card numbers never stored unredacted.
- **NFR-7 Readable UI:** legible at 1280×720 for screen recording; no JS framework.
- **NFR-8 Quality:** ruff clean; pytest; CI on GitHub Actions; README with a 60-second quickstart.
