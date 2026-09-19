# Architecture — front-desk-agents

The client-facing picture is `../../workflow.html`. This is the engineering view.

## Message lifecycle

```
InboxConnector ──► intake (store, transcribe if audio)
                     │
                     ▼
               guards.pre()  ── safety keyword? ──────────────► ALERT
                     │         card number? → redact ─────────► HUMAN (card_data)
                     │         injection pattern? ────────────► HUMAN (suspicious_instructions)
                     ▼
               triage (LLM → TriageResult, 1 retry) ── invalid ─► HUMAN (triage_failed)
                     │
                     ▼
               rules.decide()  intent=safety_urgent ──────────► ALERT
                     │         escalation.yaml match ─────────► HUMAN (<rule id>)
                     │         documents + attachment/reply ──► RECORD_UPDATE ──► BookingsConnector
                     │         spam ──────────────────────────► IGNORE
                     ▼
               drafter (LLM + tools) ──► grounding check ── fail ─► HUMAN (ungrounded / no_policy)
                     │
                     ▼
               approval queue ── approve / edit / reject ──► OutboundConnector (var/outbox)

chaser (daily, after inbox) ── reservations due at T-14/7/2 with missing items ──► approval queue
every step ──► events table ──► /log
```

## Layout
```
repo/
  app/
    main.py               FastAPI app + routes
    clock.py              fixed clock (DEMO_TODAY, TZ)
    settings.py           pydantic-settings from .env
    pipeline.py           run_inbox(), run_chaser(), run_all()
    guards.py             safety keywords, card detection/redaction, injection patterns
    rules.py              decide(): applies escalation.yaml + routing.yaml
    grounding.py          check(draft_text, tool_results, triage) -> GroundingResult
    agents/
      triage.py
      drafter.py
      chaser.py
    tools/
      availability.py     check_availability()
      pricing.py          quote()
      policy.py           get_policy() — parses config/policies.md by "## P<n>" headings
      reservations.py     get_reservation()
      payments.py         payment_link()
    llm/
      base.py             LLMProvider protocol, Message, ToolSpec, LLMResponse (tokens, latency)
      ollama.py           JSON-mode tool loop
      anthropic.py        native tool use
      fake.py             FakeProvider — returns canned responses from tests/fixtures/*.json
    connectors/
      inbox.py            InboxConnector, JsonlInbox
      bookings.py         BookingsConnector, SqliteBookings
      outbound.py         OutboundConnector, FileOutbound
      alerts.py           AlertConnector, ConsoleFileAlerts
    store/
      db.py               engine, session, reset
      models.py           SQLModel tables
    prompts/
      triage.md
      drafter.md
      chaser.md
    web/
      templates/          base.html, inbox.html, queue.html, draft.html, needs_person.html, alerts.html, log.html
      static/             app.css, app.js (vanilla)
  evals/
    run_evals.py          metrics + thresholds, writes var/eval/*.json
  scripts/
    seed.py
    demo.py               reset → seed → run_all → print summary → serve
    cost_report.py        writes docs/COST.md
  config/                 policies.md, escalation.yaml, routing.yaml, chaser.yaml, pricing.yaml
  data/                   units.csv, reservations.csv, messages.jsonl, (optional) audio/
  tests/
  var/                    runtime: app.db, outbox/, eval/ (gitignored)
```

## Data model (SQLModel)

| table | key columns |
|---|---|
| `units` | `unit_id` PK, `unit_type`, `max_length_ft`, `max_beam_ft`, `power`, `notes` |
| `reservations` | `reservation_id` PK, guest fields, `unit_type`, `unit_id`, `arrival`, `departure`, boat/RV fields, `insurance_cert`, `vessel_registration`, `signed_contract`, `deposit_paid` (each `missing` · `received_pending_review` · `ok` · `n/a`), `last_guest_contact`, `status` |
| `messages` | `message_id` PK, `channel`, `received_at`, sender fields, `subject`, `body`, `body_redacted`, `attachments` (JSON), `status` |
| `triage_results` | `message_id` FK, TriageResult JSON, model, prompt_version, tokens, latency_ms |
| `decisions` | `message_id` FK, `decision`, `team`, `reason`, `rule_id` |
| `drafts` | `draft_id` PK, `message_id` FK nullable, `reservation_id` nullable, `kind` (`reply` · `reminder`), `team`, `text`, `language`, `policy_ids_cited`, `tool_calls` JSON, `grounding` JSON, `status` (`pending` · `approved` · `rejected` · `sent`), `final_text`, `edit_distance`, `reviewed_at`, `reject_reason` |
| `alerts` | `alert_id` PK, `message_id` FK, `team`, `callback`, `summary`, `created_at`, `acknowledged_at` |
| `events` | `event_id` PK, `ts`, `message_id`, `reservation_id`, `agent`, `action`, `detail` JSON, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms` |

## Connectors (production shapes)

```python
class InboxConnector(Protocol):
    def fetch_new(self, since: datetime) -> list[InboundMessage]: ...
    # prod: Gmail API / IMAP for email; Twilio or RingCentral recording webhook + transcription for voicemail

class BookingsConnector(Protocol):
    def occupied_units(self, unit_type: str, arrival: date, departure: date) -> set[str]: ...
    def get_reservation(self, *, reservation_id=None, email=None, phone=None) -> Reservation | None: ...
    def reservations_arriving(self, on: date) -> list[Reservation]: ...
    def update_documents(self, reservation_id: str, **items: DocStatus) -> None: ...
    def record_guest_contact(self, reservation_id: str, at: datetime) -> None: ...
    # prod: the client's booking platform API (unknown — confirm in discovery)

class OutboundConnector(Protocol):
    def send(self, draft: Draft, to: str, channel: Literal["email", "sms"]) -> SendResult: ...
    # prod: Gmail send / SMTP; Twilio SMS

class AlertConnector(Protocol):
    def raise_alert(self, alert: Alert) -> None: ...
    # prod: SMS + phone call to on-duty dockmaster; Slack/Teams if used
```
Payments: `payment_link(reservation_id)` returns a stub URL. In production this is a Stripe
Payment Link or Checkout Session (the client already uses Stripe). The agent never handles card data.

## Availability logic
A unit fits if `unit_type` matches, `max_length_ft ≥ boat/RV length`, `max_beam_ft ≥ beam` (if
given), and no reservation on that unit overlaps: `arrival < other.departure and departure > other.arrival`
(the departure day is free). `seasonal_slip` units are never offered for transient requests.

## Pricing logic (`quote`)
From `config/policies.md` P2/P3/P5, mirrored as numbers in `config/pricing.yaml` → `rates`:
transient slip $3.50/ft/night with a 30-ft minimum; holiday weekends 3-night minimum; deposit =
first night. Returns strings formatted `$1,234.00` so the grounding check can match exactly.

## Grounding check
Extract from the draft: `$` amounts (normalise `$133` = `$133.00`), dates (any format → ISO), unit
ids (`[DST]\d+|RV\d+|T\d+|S\d+`). Each must appear in the union of tool results + triage fields.
Weekday names are allowed. Result: `{passed, unmatched: [...]}`.

## Dependencies
fastapi, uvicorn, jinja2, sqlmodel, pydantic>=2, pydantic-settings, pyyaml, httpx (Ollama),
anthropic, python-dateutil, rapidfuzz (edit distance), faster-whisper (optional extra `audio`),
pytest, ruff. Nothing else without a DECISIONS.md entry.
