# Video walkthrough - shot-by-shot recording script

A 2-minute screen recording with voiceover. Everything below is one continuous take in the browser;
no editing required beyond trimming the ends.

**Before you hit record**
- Open https://marina-front-desk-demo.fly.dev and sign in (so the password prompt is not on camera).
- Click **Reset demo** in the top right. Confirm the inbox reads **15 / 14 / 3 / 2 / 1**.
- Browser at 1280x720, zoom 110%, bookmarks bar hidden, one tab only.
- Have this script on a second screen or phone. Read at a normal pace - the timings assume ~150 wpm.
- The four sample buttons on `/try` are pre-cached, so they respond instantly on camera.

Total: **2:00**. If you overrun, cut shot 7 (Autonomy) first - it is the most expendable.

---

### 1 - Inbox · 0:00-0:12 · page `/`
**On screen:** land on the inbox summary. Let the counters sit for a beat, then point at them.

> "This is a marina's inbox at eight on a Monday morning. Thirty-five voicemails and emails came in
> over the weekend. Nobody has touched it yet - but the agents already have."

---

### 2 - A drafted reply · 0:12-0:38 · `/queue` then the VM01 draft
**On screen:** click **Approval queue** → open the draft for **VM01**. Scroll slowly so the tool
calls, the cited policies and the green grounding line are all visible.

> "Here's a voicemail: someone wants a slip for Labour Day weekend. The agent checked the
> reservation book, found two slips that fit his thirty-eight foot boat, and quoted your rates -
> a hundred and thirty-three a night, with the three-night holiday minimum.
> Every number in that reply came from a tool, not from the model's imagination. That's what the
> green line means. And nothing goes to the guest until someone clicks approve."

**Action:** click **Approve & send**.

---

### 3 - Safety · 0:38-0:52 · `/alerts`
**On screen:** click the red banner, then **Alerts**.

> "This one's different. A boat taking on water, nobody aboard. The agent didn't write a friendly
> reply - it refused to, and woke up the dockmaster instead, with the callback number."

**Action:** click **Acknowledge** on VM02.

---

### 4 - The chaser · 0:52-1:06 · `/reservations` then `R-1047`
**On screen:** click **Reservations**, then open **R-1047**.

> "It also chases paperwork. Four guests arriving soon are missing insurance, a registration or a
> deposit - they each get a reminder. But this guest sent his certificate in on Sunday, so the agent
> logged it and stopped chasing him. It doesn't nag people who already did the thing."

---

### 5 - Try it yourself · 1:06-1:32 · `/try`  ← **the moment that sells it**
**On screen:** click **Try it yourself**. Click the **Safety** sample button so the text fills in,
then click **Run the agents**. Let the result render.

> "Now - the obvious question. What about a message you didn't plan for? Let's find out.
> I'll type something that isn't in the demo data at all."
>
> *(after it renders)*
>
> "It read it, spotted the hazard, and sent it straight to a person. No reply drafted. This is the
> real system running live on text I just made up - not a recording."

---

### 6 - What it refuses · 1:32-1:44 · `/needs-person`
**On screen:** click **Needs a person**. Point at the EM11 and EM17 rows.

> "Fourteen messages it deliberately would not answer. A refund argument, a legal threat. Someone
> emailed a card number - it was stripped out before the AI ever saw it. And someone tried to talk
> it into handing over your guest list. It didn't."

---

### 7 - Knowing when to trust it · 1:44-1:53 · `/autonomy`
**On screen:** click **Autonomy**.

> "And this is how we'd decide to let it send anything on its own: only once your team has stopped
> editing the drafts. Measured, not assumed."

---

### 8 - Close · 1:53-2:00 · `/log`
**On screen:** click **Activity log**, let the event table and the cost figure show.

> "Every step logged, with what it cost. Happy to walk you through it properly."

---

## If you want a shorter 60-second cut
Keep shots 1, 2, 5 and 8 (inbox → drafted reply → try it yourself → log). That is the whole story:
it sorts the weekend, it drafts grounded replies you approve, it handles things nobody scripted,
and it shows its work.

## Tips
- Do not narrate the clicking ("now I'll click here"). Say what it *means*.
- Pause for a full second after each page loads before speaking - it reads calmer.
- If a page hesitates on the first click, the machine was asleep; reset and start again.
- Say "the agents" or "it", never "the AI model" - the owner cares about the outcome.
