# Demo script — "Monday morning at Lakeside Cove"

Setting: it's **Monday 24 August 2026, 8:00 am**. The office was closed Sunday. Overnight and over
the weekend, 15 voicemails and 20 emails arrived. The agents processed them before anyone came in.

Run: `make reset demo`, open http://localhost:8000. Browser at 1280×720, zoom 110%.

## Expected results (check every line before recording)

**Inbox summary (`/`)**
- 35 messages: 15 voicemail, 20 email
- Decisions: **15 drafted · 14 need a person · 3 safety alerts · 2 records updated · 1 ignored**
- Document chaser: **4 reminders drafted · 2 skipped**
- Approval queue: **19 pending** (15 replies + 4 reminders)

**Safety alerts (red banner, `/alerts`)** — all to dockmaster, no drafts
- VM02 — boat next to caller on C dock taking on water, nobody aboard
- VM03 — strong fuel smell / sheen at the fuel dock
- VM12 — guest fell from the swim dock, bleeding

**Needs a person (with reason)**
| id | reason | team |
|---|---|---|
| VM05 | `complaint_or_dispute` (charged twice) | office |
| VM08 | `cancel_or_refund` (Labour Day cancellation, R-1051) | office |
| VM09 | `seasonal_tenant` (S07 extension) | dockmaster |
| VM10 | `low_confidence` (no name, no details) | office |
| EM04 | `no_policy` (liveaboards) | office |
| EM05 | `group_booking` (6 sites) | office |
| EM06 | `complaint_or_dispute` (noise, RV3) | office |
| EM08 | `vendor_other` (ice supplier invoice) | office |
| EM09 | `urgent_service` (engine won't start, D3) | boatyard |
| EM11 | `card_data` — card number shown as `[card removed]` everywhere | office |
| EM12 | `no_policy` (wedding at pavilion) | office |
| EM13 | `payment` (receipt request) | office |
| EM17 | `suspicious_instructions` (asks for free week + guest list) | office |
| EM19 | `legal_threat` (hull damage) | office |

**Records updated** — EM01: R-1047 insurance → received, pending review · EM02: R-1052 guest contact logged
**Ignored** — VM15 (vehicle-warranty robocall)

**Key drafts**
- **VM01** (38-ft *Second Wind*, Labour Day): slips fit (available D6, D8; recommended D6) · $133.00/night · 3-night holiday minimum → $399.00 · deposit $133.00 · holiday cancellations need 30 days' notice · cites P2 P3 P4 P5 · grounding ✅
- **VM13** (R-1047 "did you get my insurance?"): confirms received on Aug 23, being reviewed
- **EM03** (24-ft boat, Aug 28–30): recommended D2, D3 (smallest slips that fit) · charged at the 30-ft minimum → $105.00/night
- **EM16** (Spanish): reply in Spanish; RV full-hookup sites available Sep 18–20 at $68.00/night

**Chaser**
- Reminders: R-1046 (vessel registration, arriving Aug 26) · R-1048 (insurance, Aug 31) · R-1050 (deposit + payment link, Aug 31) · R-1055 (rental agreement + deposit + payment link, Sep 7)
- Skipped: R-1047 `document_received` · R-1052 `guest_contacted`

## Live call version (8–10 min)
1. **Inbox summary** — "This is your inbox at 8 am. Nobody has touched it yet." Point at the counts.
2. **VM01 → draft** — play/read the voicemail; open the draft; show the tool calls (availability → D6, D8), the policies cited, the green grounding check. Click **Approve**. "One click instead of a callback and a lookup."
3. **Safety banner** — open VM02. "It didn't write anything. It woke up the dockmaster." Click Acknowledge.
4. **Chaser** — open the reminders; then show R-1047 skipped because the certificate arrived in EM01 on Sunday. "It stops chasing people who already did it."
5. **What it refused** — EM11 (card number removed before the AI saw it), EM17 (tried to talk it into a free week).
6. **Edit & approve** — change one sentence in EM03's draft, approve; show the edit score on `/log`. "This number tells us when it's safe to trust it more."
7. **Activity log + cost** — today's counts, cost in cents; open `docs/COST.md` for 100/500/2,000 a day.
8. **What it won't do yet** — live calls, payments, sending without approval. Then hand over to questions.

## Video cut (≤ 2:00)
| time | shot | line |
|---|---|---|
| 0:00 | Inbox summary | "Monday 8 am. 35 messages from the weekend — already sorted." |
| 0:15 | VM01 draft + tool panel | "Checks the reservation book, quotes your policy, shows its sources." |
| 0:40 | Approve click | "Nothing goes to a guest until your team approves it." |
| 0:50 | VM02 red banner | "Safety calls skip the queue and alert a person." |
| 1:05 | Chaser list + R-1047 skip | "Chases missing paperwork — and stops when it arrives." |
| 1:25 | EM11 redaction | "Card numbers are removed before the AI ever sees them." |
| 1:35 | `/log` | "Every step logged, with what it cost." |
| 1:50 | End card: repo link | "Built as a demo of your brief. Happy to walk you through it." |
