---
name: l-build
description: Build the tasks and report with evidence — build a work's tasks (all of W-NNN or one W-NNN-T03) in order — build → test → commit per task ([W-NNN-T03]) → check off, leaving evidence in <<file.record>> (files changed · test results · acceptance criteria · captures · schema changes); when done, show a summary of what goes into the current state and merge it after approval. Use to implement a planned work.
invocation: model
argument-hint: "W-NNN | W-NNN-T03 [--report-cycle work|criterion|task]"
---

# /l-build — build it and report with evidence

**Purpose:** build the tasks and report **with evidence, not "it's done"**.

Input: `$ARGUMENTS` — `W-012` (all) or `W-012-T03` (one). The report cycle can be changed for this work only, like `--report-cycle task`.
Current settings: report cycle `<<build.report_cycle>>` · applying to the current state `<<build.merge_approval>>`<!-- lantern:if build.test --> · tests `<<build.test>>`<!-- lantern:endif -->

## 0. Prepare
1. If `<<file.tasks>>` doesn't exist, stop and suggest running `/l-task` first. If the design approval (`approved` in `<<file.design>>`) is empty<!-- lantern:if design.approval=off -->, the gate is off, so go ahead.<!-- lantern:endif --><!-- lantern:if !design.approval=off -->, stop and go through the `/l-design` gate first.<!-- lantern:endif -->
2. One work = one branch: `lantern work branch W-012` (inside a worktree for parallel work you are already on that branch — skip it)
3. Make the work pack and read **only that** (a one-off summary of the work folder plus only the related parts of the current state):
   ```bash
   lantern pack W-012     # → .lantern/pack/W-012.md
   ```
4. If `<<file.record>>` doesn't exist, `lantern scaffold doc W-012 "<<doc.record>>"`

## 1. One task at a time (the small loop)
```bash
lantern task next W-012          # the next task that can start, in order (blocked ones are skipped, with the reason)
lantern task next W-012 --all    # every task that can start now — [P] marks tasks that can run at the same time
lantern task start W-012-T03     # stamps [<<attr.start>>:: time] exactly
```
**Parallel (graph):** if `--all` shows two or more `[P]` tasks and this tool supports subagents, you may hand the `[P]` tasks **one each** to subagents. Make each follow the same rules (start · evidence · one task = one commit), and never hand out tasks that change the same files together. Without subagent support, do them in turn.

1. Build it. If a **big change** not in the design is needed, stop and report (→ `/l-design`).
2. Test it<!-- lantern:if build.lint -->, and run lint and type check too (`lantern lint`)<!-- lantern:endif -->. On failure, fix and retry — **at most 3 times**. If the third try fails, stop and report.
3. Leave evidence in `<<file.record>>`:
   - One line in the `## Evidence` table: task · commit (filled after committing) · files changed · test results (command and pass count) · acceptance criteria
   - For screens, save a capture to `<<folder.screens>>/build/` and write its path
   - If the schema changed, one line in `## <<section.schema>>` (date · change · why/ADR · migration file) — **if a migration has to run against a real database, stop and ask**
   - Overwrite `## <<section.now>>` (progress · next · blocked, 3–5 lines)
4. Check it off and commit:
   ```bash
   lantern task done W-012-T03      # [<<attr.finish>>:: time] + acceptance-criterion checkpoint notice
   ```
<!-- lantern:if docs.remote=shared -->
   Code + `<<file.tasks>>` + `<<file.record>>` **in one commit**: `git add … && git commit -m "feat: <what> [W-012-T03]"` (follow the user's commit rules, with the ID at the end). After committing, fill the commit column of the evidence table and include it in the next commit.
<!-- lantern:endif -->
<!-- lantern:if docs.remote=local -->
   Code commit `git commit -m "feat: <what> [W-012-T03]"` → then a docs commit pointing to it: `git -C docs add -A && git -C docs commit -m "docs: W-012-T03 log (code $(git rev-parse --short HEAD))"`. Never put `docs/` in a code commit.
<!-- lantern:endif -->
   Don't mix several tasks in one commit. A big task may have several commits with the same ID.
5. **Acceptance-criterion checkpoint:** when `task done` announces a checkpoint for `AC-1`, check that AC on its own (related tests · trying the behavior). If it passes, `lantern task ac W-012 AC-1`.

<!-- lantern:if plan.ui_reference=required -->
6. **Check against the mockup:** when a `[<<attr.screen>>:: …]` task is done, capture the built screen (`<<folder.screens>>/build/…png`); if the mockup is a PNG too, point out the differences first with the automatic comparison: `lantern screen compare "<<folder.screens>>/build/login.png" "<<folder.screens>>/login.png"` (a hint only). Then **show both side by side and ask the user**: "Does it match the mockup?" → if it does, check off the AC; if not, for each difference `lantern task add W-012 "<fix the difference>" --size S --ac AC-n --screen "<screen>"`.
<!-- lantern:endif -->

## 2. When to report
- `work`: when the whole work is done · `criterion`: each time an acceptance criterion is complete · `task`: after each task
- **Report and stop right away, whatever the setting:** tests still fail after 3 fixes · you hit a `<<marker.unknown>>` · checking a screen against its mockup · running a migration against a real database · a big change not in the design
- A report is 3 lines: **what was done · why it stopped · what needs choosing**

<!-- lantern:if knowledge -->
## 3. New technologies · libraries → /l-learn candidates
When a new technology comes in while building, collect it as a candidate (leave out ones with notes and known tech, at most <<learn.max_candidates>>). **Don't stop the work**; show them in the final report. Small library choices get one line in the decisions section of `<<file.record>>`; hard-to-reverse choices go to `/l-adr`.
<!-- lantern:endif -->

<!-- lantern:if build.loop=on -->
## 3½. The big loop (build.loop: on · at most <<build.loop_limit>> times)
When every task is done, run all the acceptance tests together<!-- lantern:if build.test --> (`<<build.test>>`)<!-- lantern:endif -->.
- All pass → step 4.
- Any acceptance criterion fails → add a task to fix each failure (`lantern task add W-012 "<make AC-n pass>" --size S --ac AC-n`) and go round again from step 1. Write in `<<file.record>>`: "big loop round n: failing ACs · the cause in one line".
- If they still fail after <<build.loop_limit>> rounds, stop and report (what was done · remaining failures · what needs choosing).
<!-- lantern:endif -->

## 4. When everything is done — apply to the current state
When `lantern task next W-012` says every task is done:
1. Show **one summary** of the design changes to merge into the current state:
   ```
   📘 Feature List  ✚ Sign in with Google (W-012)
   🏗 Architecture  ✎ add Google OAuth to the sign-in flow
   🗄 Data          ✚ users.google_id   (⚠ data structure change)
   🔌 API           —
   → [Apply all] / [Pick what to apply] / [Change something]
   ```
   - `required`: always ask. `auto`: apply first, then report the summary (undo with git if wrong).
   - **Data structure and API changes are always asked about, whatever the setting.**
2. Apply it: each fact in one place — link the work it came from.
   - Data: merge the design's DBML changes into `<<folder.current>>/<<folder.data>>/schema.dbml` → `lantern check-dbml` → `lantern dbml render`
   - When each applied document was checked: `lantern meta set "<document>" checked_commit=$(git rev-parse --short HEAD)` (and `code` if more code paths are involved)
3. Merge the work branch into the base branch and clean up (test → merge → clean up):
   ```bash
   lantern work finish W-012
   lantern work archive W-012      # work folder → <<folder.archive>>/ (links are fixed too)
   ```
4. Common wrap-up + drift check + refresh the report:
   ```bash
   lantern close l-build --work W-012
   lantern scan
   lantern report
   ```
5. Final report: evidence summary (tasks · commits · tests · ACs) · what was applied · drift found by `scan` · debt candidates · the next task.
