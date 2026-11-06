---
name: l-design
description: Design how to build it — write only what changes in a work (W-NNN) into <<file.design>> as structure (Mermaid) · screens (Claude Design mockup files) · data (DBML changes + a migration plan), hand hard-to-reverse choices to a decision record (ADR), and get the person's approval (the design gate). Use after /l-plan when a work needs a design.
invocation: model
argument-hint: "W-NNN"
---

# /l-design — how to build it (structure · screens · data)

**Purpose:** design **only what changes** in this work. Don't rewrite the whole current system.

Input: `$ARGUMENTS` — `W-012`.

## 0. Before starting
- Read `<<file.plan>>`. **If any `<<marker.unknown>>` remains, ask first** (at most <<plan.max_questions>>, highest impact first).
- Read only the related parts of the current state: `<<folder.current>>/<<file.architecture>>` · `<<folder.screens>>/` · `<<folder.data>>/schema.dbml`.
- When a design choice depends on domain rules, read only the sections tied to the work (`lantern ref domain --work W-012`) with `lantern ref read` — don't skim the whole index again.

## 1. Create <<file.design>> · pick sections
```bash
lantern scaffold doc W-012 "<<doc.design>>"
```
Of the three sections, keep **only the ones this work needs** (e.g. screens only, data only). List them in frontmatter `parts` (e.g. `[structure, data]`). Delete unused sections whole. Never delete "<<marker.glance>>" or "Hard-to-reverse choices".

## 2. 🏗 Structure
Draw the parts and flows that change in Mermaid. The text explains the diagram. Write code locations in backticks like `` `src/…` `` (they are used to warn about clashes between parallel works).

## 3. 🎨 Screens
<!-- lantern:if design.tool=claude-design -->
**If Claude's Design tool is available** (the artifact tool has a Design type), make the wireframes yourself.
1. Take the list of screens from the user scenarios and acceptance criteria in `<<file.plan>>`.
2. Make one Design canvas named after the work, with one board per screen. Follow the design system if there is one.
   Draw boards as static markup with no live values, so the saved file opens on its own outside the canvas.
   - If the work changes an existing screen, keep the screen before the change first: capture the running screen, or redraw it on the canvas from its code, and save it in `<<folder.screens>>/<<folder.screens_current>>/` (this folder doesn't count as a mockup). Draw the changed screen on the next board of the same canvas.
   - If there's no design system and the code has shared UI parts, mention it once: "If you move the existing buttons, colors and fonts into a Claude design system, the mockups come out looking like the current app. If you'd like that, run `/design-sync`."
3. Also save each board file (`.dc.html`) in `<<folder.works>>/W-012 …/<<folder.screens>>/`. Note the canvas link in the design for reference.
4. Show the person the canvas link and get it confirmed. If a requirement turns out missing, fix the acceptance criteria in `<<file.plan>>` first, then redo the screens.
   If the person edited the canvas themselves, read those files again and update the files in `<<folder.screens>>/`.

**If it isn't available** (Codex, Antigravity and so on), get the mockups from the person: "Please make the screens in Claude, **export them as HTML** and put them in the `<<folder.screens>>/` folder". If you get a Claude Code handoff bundle (zip · folder), unpack it under `<<folder.screens>>/` with `lantern screen import W-012 <bundle>`.
<!-- lantern:endif -->
<!-- lantern:if design.tool=figma -->
Read the frame through the Figma MCP server (Dev Mode MCP) → **export the frame as an image** and save it in `<<folder.works>>/W-012 …/<<folder.screens>>/` (`lantern screen import W-012 <file · folder>`). Copy the values needed to build it (colors · spacing · component names) from the MCP into the design's tables. Don't stop at a Figma link — the **file** that teammates and the AI can open is the source.
<!-- lantern:endif -->
<!-- lantern:if design.tool=canva -->
Find the design through the Canva MCP server and **export it as PNG or PDF** into `<<folder.works>>/W-012 …/<<folder.screens>>/` (`lantern screen import W-012 <file · folder>`). Don't stop at a share link.
<!-- lantern:endif -->
<!-- lantern:if design.tool=none -->
Keep mockups as wireframes · reference images · HTML files in `<<folder.works>>/W-012 …/<<folder.screens>>/`.
<!-- lantern:endif -->
**Don't stop at a link** (it may change later or not open outside the organization). Note links for reference; the **files** in `<<folder.screens>>/` are the source, and the design text explains them. List screen · mockup file · notes in the table.
<!-- lantern:if plan.ui_reference=required -->
Once the mockups are in, add an acceptance criterion to `<<file.plan>>`: `- [ ] AC-n Result: the screen matches the mockup screens/<file>`
<!-- lantern:endif -->

## 4. 🗄 Data
- Write only the **changes** against the current ERD (`<<folder.current>>/<<folder.data>>/schema.dbml`) in a ```` ```dbml ```` block (changed tables as complete definitions).
- Write the change table (add · change · remove) and the **migration plan**.
- Check: `lantern check-dbml "docs/<<folder.works>>/W-012 …/<<file.design>>"` (merges with the current schema.dbml to check references)
- On-device storage of apps without a server uses the same DBML.

## 5. Hard-to-reverse choices → /l-adr
**Record:** tool choices that are hard to change (database · framework · auth method · outside service) · data structure changes · public API changes · decisions that changed direction. **Don't record:** small libraries (one line in `<<file.record>>`) · code cleanup.
Check question: "in six months, will someone ask 'why did we do this?'" — the AI **only suggests**; the person decides whether to record it. But **data structure changes are always** recorded. To record one, call `/l-adr` and add the ID to `adr` in <<file.design>>'s frontmatter.

## 6. The design gate — current setting: design.approval = <<design.approval>>
The approval screen is a **3-line summary** + choices:
```
🏗 Structure: …   🎨 Screens: …   🗄 Data: …   (⚠ hard to reverse: …)
→ [Go ahead] / [Change something]
```
- `required`: always ask.
- `auto`: for small designs **without** data changes or ADRs, don't ask; report in one line.
- `off`: don't ask.
- **With a data structure change or an ADR, always ask, whatever the setting.**

Once approved (or passed by auto), record it:
```bash
lantern design approve W-012 --by "<who approved>"     # --by auto when passed by auto
```
If told what to change, change it and show the summary again.

When the project has domain knowledge (`lantern ref domain` isn't empty), add one line to the approval screen: `📚 Domain knowledge used: N — anything needed that's missing?` Tie what you hear with `lantern ref attach`.

<!-- lantern:if knowledge -->
## 7. Unfamiliar technologies → /l-learn candidates
When the design brings in a new technology or library, gather candidates by the same rules as /l-plan (leave out ones with notes, at most <<learn.max_candidates>>, don't stop the work).
<!-- lantern:endif -->

## Common wrap-up
```bash
lantern close l-design --work W-012
```
**Next:** `/l-task W-012`.
