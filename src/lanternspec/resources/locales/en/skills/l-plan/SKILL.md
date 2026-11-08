---
name: l-plan
description: Turn an idea into a work (plan) — decide what to build and why, and create the work folder docs/<<folder.works>>/W-NNN and <<file.plan>> (<<marker.glance>> · what · why · user scenario · acceptance criteria · out of scope). Unknowns are marked <<marker.unknown>> and asked about. Use when the user decides to build an idea (IDEA-NNN) or describes a feature to plan.
invocation: model
argument-hint: "IDEA-NNN | <what to build>"
---

# /l-plan — turn an idea into a work (plan)

**Purpose:** decide **what and why**, and create the work folder. How (the design) is the next step.

Input: `$ARGUMENTS` — `IDEA-014`, or a description.

## 0. Read (only as much as needed)
- `lantern status` — works in progress
- The <<marker.glance>> of `docs/<<folder.current>>/<<file.project_definition>>` · `<<file.features>>`
- The idea card (for `IDEA-014`). If it is <<idea_status.blocked.label>>, first give why it is blocked and what would reopen it, and confirm with the person that this has happened. If the card links a source document (a diagnosis, a report), read only the items the card names from it
- `docs/<<folder.rules>>/<<file.unit_log>>` — why people changed the recommendation before

## 1. Suggest a work unit → the person chooses
Why works are divided: grouping work of the same kind **keeps the AI from touching things outside the purpose**, and later anyone can **tell what was done** from the list of works alone.

**Rule — one work = one purpose.** The work's name must say in one line "what changes, and for what". If that line needs an "and", there are two purposes.

Compare with the names and purposes of the open works (`lantern status`) and present one of three as **a recommendation with the reason**:
- **New work** — when the idea's purpose fits none of the open works' purposes. Create one work for that one purpose (e.g. "Add a job filter to the posting list").
- **Add to an existing work** — the target is **a work not finished yet** (planning · design · in progress), when the new part is explained without changing that work's name (purpose). The same holds for a new idea and for tasks that turn up while planning or building. Never add to a finished, archived work — make a new one.
- **Divide and place** — when one idea has several purposes. Show in a table where each piece goes (an existing work / a new work) and why:
  ```
  | Piece                  | Goes to                          | Why                                          |
  | Job · region filter UI | New work "Posting list filter"   | A screen feature — no open work has this purpose |
  | Region name cleanup    | Existing W-010 "Data cleanup"    | Fits W-010's purpose (standard names)        |
  ```
  If the person agrees, create them as shown; otherwise move or merge pieces until it fits.

If the person chooses differently from the recommendation, ask why and record it:
```bash
lantern unit-log add --what "<what>" --recommended "<recommendation>" --chosen "<the person's choice>" --reason "<why>"
```

## 2. Create the work folder
```bash
lantern idea status IDEA-014 "<<idea_status.reviewing>>"   # when starting from an idea
lantern scaffold work "<work name>" --idea IDEA-014 [--ui] [--branch "<branch name>"]  # --ui for work that changes screens
lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-012
```
- The branch naming rule is `<<git.branch>>`. If it has blanks other than `{id}`, settle the name with the person, pass it with `--branch`. The closing `lantern close` commits the documents on the current branch (the base branch), so other branches can tell this work's branch. With only `{id}`, don't pass it.
- When starting **without an idea**, create the idea card along the way: `lantern scaffold idea "<name>" --raw "<the user's description>" --status "<<idea_status.worked>>"` → `scaffold work --idea` with that ID → `idea status … "<<idea_status.worked>>" --work …`.
- To **add to an existing work**, don't create a folder; add the scenario and acceptance criteria to that work's `<<file.plan>>`, then `lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-010`.
- To **divide and place**, do one of the two above for each piece: create a folder for a new-work piece, add an existing-work piece to that work's `<<file.plan>>`. Then run `lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-0NN` once per work (each run adds one work link to the idea).

## 3. Fill <<file.plan>>
<<marker.glance>> · what · why · user scenario · **acceptance criteria** · out of scope, and frontmatter `domain` (one word for the feature domain).
<!-- lantern:if plan.ac_format=gwt -->
Acceptance criteria format (Given–When–Then): `- [ ] AC-1 Given: … · When: … · Then: …` — Given only when needed, one per line.
<!-- lantern:endif -->
<!-- lantern:if plan.ac_format=simple -->
Acceptance criteria format: `- [ ] AC-1 When …, then …` — one per line.
<!-- lantern:endif -->
Make results **checkable**: "fast" ✕ → "within 2 seconds" ○, "shows well" ✕ → "shows at the top of the list" ○.

**Pick domain knowledge:** look at "When to read" in `lantern ref domain` (the index) and **only pick, without reading**, the sections this work needs — they are read when their task starts. For each one:
```bash
lantern ref attach "<address>" --work W-012 --note "what it is for"
```
Inside material gets a line in `## <<section.domain_refs>>`; outside material stays only in this computer's `.lantern/`. Don't write that section by hand. Leave it empty when nothing applies.

## 4. Ask about what you don't know (no guessing)
Write unknowns in their section as `<<marker.unknown>>: <question>`, and ask **at most <<plan.max_questions>> at a time**.
- Pick by impact: scope → security → user experience → details
- If there are few unknowns, ask only those. **Never make up questions.**
- Leave the remaining questions as `<<marker.unknown>>` and ask again before `/l-design`.
Once answered, put the answer in its section and delete the `❓` line.

## 5. Check the acceptance criteria
```bash
lantern check --epic W-012
```
Fix ⚠ vague words · several meanings · format warnings. If you can't tell what was meant, ask the person.

## 6. Screens (work that changes screens)
Work that changes screens has `ui: true` (`--ui`). In the user scenarios, write **the screens needed and what each one does** (e.g. "Sign-in screen — enter an email and password and sign in").
Don't make wireframes here. `/l-design` makes them from this list and the acceptance criteria.
<!-- lantern:if plan.ui_reference=required -->
This project needs a mockup before building screen work (`plan.ui_reference: required`). `/l-design` adds the mockup and the "the screen matches the mockup" acceptance criterion.
<!-- lantern:endif -->

<!-- lantern:if knowledge -->
## 7. Unfamiliar technologies → /l-learn candidates
When the plan mentions technical terms, pick candidates: with `lantern debt find "<term>"` (known tech · existing cards) and `lantern knowledge search "<term>"`, **leave out terms that already have a note.** At most <<learn.max_candidates>> at a time; show them in the final report and **don't stop the work.** If the user picks some, hand them to `/l-learn`. For "I know this one", `lantern debt known add "<term>"`.
<!-- lantern:endif -->

## Common wrap-up
```bash
lantern close l-plan --work W-012 --commit
```
A 3-line report: the work created · remaining `<<marker.unknown>>` · next `/l-design W-012`.
