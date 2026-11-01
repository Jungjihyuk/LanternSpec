# /l-ref rules — choose where each rule applies and how strongly

Only **approved sections** of company rules reach the AI. Propose two things per section; the person approves.

| Choose | Value | Meaning |
|---|---|---|
| Scope `--scope` | `all` | The whole project → the root AGENTS.md |
| | a part's folder (e.g. `backend`) | Only in that part → that part's AGENTS.md |
| | a language (e.g. `python`) | Only in code of that language → every part using it |
| Strength `--strength` | `must` | Must follow — kept word for word even when space is short |
| | `should` | Follow where you can — when space is short, only the title and the read command stay |

Without two or more parts everything goes to the root AGENTS.md whatever the scope. A wrong scope gets an error listing the ones you can use.

## 1. Propose
- Handle only the `+` · `~` sections of step 3's output. Read a section with `lantern ref read "<address>"` (outside material too).
- One line per section: `address — scope · strength — why`.
  - Scope, from what the section is about (e.g. "API responses" → the server part, "SQL" → that language or part).
  - Strength, from the wording ("always · never" → must, "prefer · where possible" → should). When unsure, should.
- Sections that aren't rules (preface · contents · revision history) are not proposed; list them apart as "sections to leave out".
- When smaller sections under a big one differ in scope, propose each; when they are the same, propose the big one.

## 2. Store what was approved
Store it as the person corrected it. Don't store sections that weren't approved.
```bash
lantern ref tag "<address>" --scope <scope> --strength <must|should>
lantern ref tag "<address>" --off          # take the approval away
lantern ref exclude "<address>"            # doesn't fit this project — never reaches the AI, approved or not
```
- A `~` section (changed) keeps its approval. Show what changed and only ask whether scope and strength stay.
- `exclude` is kept in `lantern.yaml` for inside material (shared with the team), in `.lantern/` for outside material (yours only). Write the reason in one line in the work record.

## 3. Put them into AGENTS.md
```bash
lantern upgrade
```
- Inside rules go word for word into the "Company rules" section of their scope's AGENTS.md.
- Outside rules put only a `lantern ref rules` line into AGENTS.md, with no content. Their words are printed by that command, on this computer only.
  The first approved outside rule sets `references.outside_rules: true` in `lantern.yaml` (only the fact that such rules exist — no path or title). Teammates see the same line, and one without the material is told how to get it. To stop following them, a person sets it to `false`.
- A ⚠ about the budget means should rules already became titles only. Look with the person at whether there are too many must rules.
