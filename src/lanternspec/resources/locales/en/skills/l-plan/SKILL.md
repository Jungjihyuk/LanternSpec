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
- The idea card (for `IDEA-014`)
- `docs/<<folder.rules>>/<<file.unit_log>>` — why people changed the recommendation before

## 1. Suggest a work unit → the person chooses
Check for overlap with open works and present one of three as **a recommendation with the reason**:
- **New work** — one result the user can see, small enough to finish and ship alone
- **Add to an existing work** — when an open work changes the same screens or the same data
- **Split in two** — when it looks like 10+ tasks or it spans several areas

If the person chooses differently from the recommendation, ask why and record it:
```bash
lantern unit-log add --what "<what>" --recommended "<recommendation>" --chosen "<the person's choice>" --reason "<why>"
```

## 2. Create the work folder
```bash
lantern idea status IDEA-014 "<<idea_status.reviewing>>"   # when starting from an idea
lantern scaffold work "<work name>" --idea IDEA-014 [--ui]  # --ui for work that changes screens
lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-012
```
- When starting **without an idea**, create the idea card along the way: `lantern scaffold idea "<name>" --raw "<the user's description>" --status "<<idea_status.worked>>"` → `scaffold work --idea` with that ID → `idea status … "<<idea_status.worked>>" --work …`.
- To **add to an existing work**, don't create a folder; add the scenario and acceptance criteria to that work's `<<file.plan>>`, then `lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-010`.

## 3. Fill <<file.plan>>
<<marker.glance>> · what · why · user scenario · **acceptance criteria** · out of scope, and frontmatter `domain` (one word for the feature domain).
<!-- lantern:if plan.ac_format=gwt -->
Acceptance criteria format (Given–When–Then): `- [ ] AC-1 Given: … · When: … · Then: …` — Given only when needed, one per line.
<!-- lantern:endif -->
<!-- lantern:if plan.ac_format=simple -->
Acceptance criteria format: `- [ ] AC-1 When …, then …` — one per line.
<!-- lantern:endif -->
Make results **checkable**: "fast" ✕ → "within 2 seconds" ○, "shows well" ✕ → "shows at the top of the list" ○.

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

<!-- lantern:if plan.ui_reference=required -->
## 6. Screen mockups (plan.ui_reference: required)
Work that changes screens has `ui: true` (`--ui`) and **needs a mockup** to proceed. Accepted as a mockup: images (wireframes · references) or HTML files (Claude Design · artifact exports) under `<<folder.works>>/W-012 …/<<folder.screens>>/`. Share links are not accepted.
- If there is none, ask for one<!-- lantern:if design.tool=claude-design -->: "Please make the screen in Claude Design, **export it as HTML** and put it in the `<<folder.screens>>/` folder"<!-- lantern:endif --><!-- lantern:if design.tool=figma -->: export the frame as an image with the Figma MCP, then `lantern screen import W-012 <file>`<!-- lantern:endif --><!-- lantern:if design.tool=canva -->: export as PNG · PDF with the Canva MCP, then `lantern screen import W-012 <file>`<!-- lantern:endif -->.
- Add to the acceptance criteria automatically: `- [ ] AC-n Then: the screen matches the <<folder.screens>>/<file> mockup`
<!-- lantern:endif -->

<!-- lantern:if knowledge -->
## 7. Unfamiliar technologies → /l-learn candidates
When the plan mentions technical terms, pick candidates: with `lantern debt find "<term>"` (known tech · existing cards) and `lantern knowledge search "<term>"`, **leave out terms that already have a note.** At most <<learn.max_candidates>> at a time; show them in the final report and **don't stop the work.** If the user picks some, hand them to `/l-learn`. For "I know this one", `lantern debt known add "<term>"`.
<!-- lantern:endif -->

## Common wrap-up
```bash
lantern close l-plan --work W-012
```
A 3-line report: the work created · remaining `<<marker.unknown>>` · next `/l-design W-012`.
