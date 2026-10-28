---
name: l-learn
description: Compare an unfamiliar technology with your knowledge store — look up technical terms in the knowledge store (Obsidian), sort them into 🟢 has a note · 🟡 has a note but asked again · 🔴 no note, create understanding-debt cards (<<folder.debt_cards>>/D-NNN) or count another ask, and suggest what to review and what to learn (learning-note drafts). Use when the user asks what a technology is, or when /l-plan · /l-design · /l-build hand over unfamiliar terms.
invocation: model
argument-hint: "<technical term> [term …]"
---

# /l-learn — compare an unfamiliar technology with your knowledge store

**Purpose:** find understanding debt, keep it in the ledger, and suggest review and study. "How many times was it asked · is it understood" lives **entirely in our ledger**. The knowledge store is read-only, except for new notes the user approves.

Input: `$ARGUMENTS` — one term or a list. They may be candidates handed over by `/l-plan` · `/l-design` · `/l-build` (then with the work ID).

<!-- lantern:if !knowledge -->
> ⚠ This project has no knowledge store, so the learning line is off. Tell the user and ask whether to run `/l-init` again to set up `knowledge`. Until then, only explain the term; don't create cards.
<!-- lantern:endif -->
<!-- lantern:if knowledge -->
## Steps (for each term)
1. **Check known tech · existing cards:**
   ```bash
   lantern debt find "<term>"            # if it is known tech, stop — don't ask again
   ```
2. **Search with the knowledge connector:**
   ```bash
   lantern knowledge search "<term>" --alias "<alias>" --json
   ```
   (Treat **aliases as the same technology**, like JWT · JSON Web Token.)
3. **Sort:**
   - 🟢 has a note, first ask → just link the note
   - 🟡 has a note but asked again (a card already exists) → suggest a review
   - 🔴 no note → suggest a learning-note draft
   - From candidates handed over by other skills, **leave out terms that already have a note**
4. **Create or update the debt card** (the script does the numbering and counting — an ask counts once per conversation):
   ```bash
   # no card yet
   lantern debt new "<term>" --area <topic> --alias "<alias>" [--work W-012] [--note "<note location>"] --session "<<SESSION_ID>>" --context "<where it came up, one line>"
   # card exists
   lantern debt ask <D-NNN> [--work W-012] --session "<<SESSION_ID>>" --context "<context>"
   ```
   - The **topic** is one of `area` in `enums.yaml` (backend · frontend · data · ai · infra · other). One topic per card. If none fits, use `other` and suggest a new topic (once the user approves, add it to `enums.yaml`).
   - Asking again about a <<debt_status.resolved.label>> card makes the script reopen it (<<debt_status.resolved.label>> → <<debt_status.asked_again.label>>).
   - Fill the card's "<<marker.glance>>" with one line on what the technology is and why it is used.
5. **Suggest:**
   - 🟡 → read the note (`lantern knowledge read "<path>"`) and give the note link + 2–3 points to review
   - 🔴 → create a learning-note draft:
     ```bash
     lantern knowledge propose "<term>" --area <topic>
     ```
     Fill the blanks of the created draft (`<<folder.note_drafts>>/…`), show it and ask for approval.
     - Current store write mode: `<<knowledge.write>>` — with `direct`, after approval `lantern knowledge write "<draft path>"`; with `propose_only`, only give the draft path and the user adds it themselves.
     - Once there is a note, link it to the card: `lantern meta set "<card>" note="<note location>"`

## "I understand it now" — current setting: learn.verify = <<learn.verify>>
- `self`: when the user says they understand, `lantern debt resolve <D-NNN>` right away
- `explain`: "Can you explain it in one line?" → compare with the note and point out what is missing → if it's fine, `lantern debt resolve <D-NNN>`. Write the explanation in the card's "What I understand now".
- After resolving, ask once whether to turn it into **competency debt** — "want to build it yourself?" (understanding first, then competency). If yes:
  ```bash
  lantern debt promote <D-NNN>              # a <<debt_kind.competency.label>> card (source: the <<debt_kind.understanding>> card)
  ```
  Agree on 1–3 small, checkable tasks in the competency card's "Practice tasks". Each time the user builds something,
  `lantern debt practice <competency D-NNN> "<what was built · link · one-line takeaway>"` (<<debt_status.practicing.label>>); when the tasks are done, `lantern debt resolve <competency D-NNN>`.

## Tech debt (debt left in the code)
Ordinary tech debt belongs to existing tools, but if the user wants it recorded, keep it in the same ledger: `lantern debt new "<what>" --kind "<<debt_kind.tech>>" --area <topic> [--work W-012]`.

## "I know this one"
When the user says it's familiar, `lantern debt known add "<term>" --alias "<alias>"` — it won't be asked about again.

## Noticing questions in the conversation — current setting: learn.detect = <<learn.detect>>
- `manual`: count only when `/l-learn` is called or another skill hands terms over.
- (In tools with agent hooks installed — Claude Code · Codex · Antigravity — with `ask` · `auto` the hook notices questions and tells you with a `LanternSpec tech question` message. Follow that message.)
<!-- lantern:if learn.detect=ask -->
- `ask`: whenever you notice a tech question like "what is JWT?", answer it, then ask in one line: "📒 Keep this as debt?"
<!-- lantern:endif -->
<!-- lantern:if learn.detect=auto -->
- `auto`: when you notice a tech question — if there is **no** card, suggest making one in one line; if there **is** one, count it with `lantern debt ask` without asking.
<!-- lantern:endif -->

## Candidates shown at a time
At most <<learn.max_candidates>>. The rest together at the end of the work.

## Common wrap-up
```bash
lantern close l-learn [--work W-012]
```
One line per result: `<<debt_status.asked_again.icon>> D-002 JWT refresh — <<debt_status.asked_again>> (3rd time) · review: [[note]]`
<!-- lantern:endif -->
