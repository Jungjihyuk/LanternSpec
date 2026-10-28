---
name: l-report
description: See where things stand, in the views you want — read the work folders · current state · debt ledger and write kanban · timeline (Mermaid gantt) · by domain · trace (idea → work → commit) · debt status · docs-vs-code into <<folder.reports>>/<<file.report>>, with a 3-line report for the lead at the top. Use when the user asks for status, progress, a kanban, a timeline or a report.
invocation: model
argument-hint: "[kanban,timeline,domain,trace,debt,sync]"
---

# /l-report — see where things stand, in the views you want

**Purpose:** **read** the documents and show them on one screen. The script draws the tables and Mermaid as text; you write **only the 3-line report for the lead**.

Input: `$ARGUMENTS` — the views to show. If none, the profile default (<<report.views>>).

| View | Name |
|---|---|
| 🗂 Kanban | `kanban` |
| 📅 Timeline (WBS) | `timeline` |
| 🧩 By domain · requirement | `domain` |
| 🔗 Trace (idea → work → commit) | `trace` |
| 📒 Debt status | `debt` |
| 🔄 Docs vs code | `sync` |
| 📊 AI work evaluation (which setup helped the outcome) | `eval` |

## Steps
1. Build the views:
   ```bash
   lantern report [--views kanban,timeline,sync]
   ```
2. Read the created `docs/<<folder.reports>>/<<file.report>>` — especially "<<marker.glance>>" and the comparison with the previous report.
3. Write **the 3-line report for the lead** (facts only, in numbers):
   1. Progress — what is done · in progress (e.g. "W-012 Sign in with Google: tasks 5/7, +3 since the last report")
   2. Risks · blockers — designs waiting for approval · <<marker.unknown>> · docs-vs-code drift
   3. Learning · next — new debt · resolved debt · what comes next
   ```bash
   lantern report --views <same views> --summary "<line 1>" "<line 2>" "<line 3>"
   ```
   (Running it again the same day overwrites that day's past report.)
4. Show the user the 3 lines and where the file is. Don't paste the whole tables into the conversation.
5. If you built the `eval` view, add one line: what the run log shows (e.g. "with design approval required, more runs finished without errors") + if the work mode `lantern harness suggest` recommends differs from the current setting, say so.

## Common wrap-up
```bash
lantern close l-report --no-check
```
