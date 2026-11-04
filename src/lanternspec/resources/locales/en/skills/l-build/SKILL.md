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
2. One work = one branch: `lantern work branch W-012` (inside a worktree for parallel work you are already on that branch — skip it). A new branch starts from the base branch `<<git.base>>`. If it stops because you are on another branch, ask the person: move to the base branch, or build on that branch (`--from <branch>` — that branch's code gets merged along with this work). If it stops because the naming rule (`<<git.branch>>`) has blanks to fill, settle a name with the person and add `--name <name>`. If `⚠ origin/…` shows up, ask whether to pull the base branch first.
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

**Domain knowledge:** when some is tied to the task, read **only those sections, right as it starts** — run the `lantern ref read …` lines that `lantern ref domain --work W-012 --task T03` shows.
Read a 📌 verbatim section again right before turning its rule into code. Knowledge that becomes necessary mid-build: find and read it with `/l-domain`, then tie it with `lantern ref attach`.

1. Build it. When something not in the design comes up, sort it with "Things outside the plan" below before changing anything.
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
   Commit message format (if the user has commit rules, follow them, with the ID at the end):
```
<<commit.template>>
```
<!-- lantern:if docs.remote=shared -->
   Code + `<<file.tasks>>` + `<<file.record>>` **in one commit**: `git add … && git commit -m "feat: <what> [W-012-T03]"` (follow the user's commit rules, with the ID at the end). After committing, fill the commit column of the evidence table and include it in the next commit.
<!-- lantern:endif -->
<!-- lantern:if docs.remote=local -->
   Code commit `git commit -m "feat: <what> [W-012-T03]"` → then a docs commit pointing to it: `git -C docs add -A && git -C docs commit -m "docs: W-012-T03 log (code $(git rev-parse --short HEAD))"`. Never put `docs/` in a code commit.
<!-- lantern:endif -->
   Don't mix several tasks in one commit. A big task may have several commits with the same ID. Don't put any mark that AI did the work (`Co-Authored-By` · `Generated with …` and so on) in the commit message.
5. **Acceptance-criterion checkpoint:** when `task done` announces a checkpoint for `AC-1`, check that AC on its own (related tests · trying the behavior). If it passes, `lantern task ac W-012 AC-1`.

<!-- lantern:if plan.ui_reference=required -->
6. **Check against the mockup:** when a `[<<attr.screen>>:: …]` task is done, capture the built screen (`<<folder.screens>>/build/…png`); if the mockup is a PNG too, point out the differences first with the automatic comparison: `lantern screen compare "<<folder.screens>>/build/login.png" "<<folder.screens>>/login.png"` (a hint only). Then **show both side by side and ask the user**: "Does it match the mockup?" → if it does, check off the AC; if not, for each difference `lantern task add W-012 "<fix the difference>" --size S --ac AC-n --screen "<screen>"`.
<!-- lantern:endif -->

## 1½. Things outside the plan
**Is it inside this work's purpose?** Inside if the purpose in the work's name explains it, otherwise outside. Something that looks like a fit for another open work is still outside — don't move it there.

| Situation | What to do |
|---|---|
| Inside, a **big change** not in the design | Stop and report (→ `/l-design`) |
| Inside, a **small difference** from the design | Go on. Bring `<<file.design>>` in line with reality, or note the difference in `<<file.record>>` |
| Outside, and **this task's acceptance criteria can be met without fixing it** | Don't fix it: leave a card and go on, even if it's a one-line fix |
| Outside, and **the acceptance criteria can't be met without fixing it** | Stop and go to "Something must come first" |

**Leaving a card:** don't do it yourself: **hand it to one subagent** and keep working (even if it looks simple). Only if this tool has no subagents, do it on the spot. A subagent doesn't know this conversation, so pass what was found, its `file:line` and the work ID in full, along with these steps:
```bash
lantern idea find "<two or three key words>"     # if the same card exists, add to its ## <<section.raw>> with the date and stop
lantern scaffold idea "<short title>" --kind <kind> --raw "Found while building W-012 (<file:line>): <what>" --auto
```
Fill in the one-line summary and why it's good in the new file; write `<<marker.unknown>>` for what you don't know, and remove optional sections with nothing to say. Keep the card out of the task's commit: commit it separately as `docs: record IDEA-NNN` (the subagent doesn't commit), and include the IDEA ID in the final report.

**Something must come first:**
1. Write why it stopped in `## <<section.now>>` and commit the changes so far to the work branch (don't check the task off).
2. Ask the person where to start. Recommend moving to the base branch `<<git.base>>`; unfinished code doesn't get merged into it. For an outage of a running service, also offer starting from the deploy branch (<!-- lantern:if git.pr=deploy -->`<<git.deploy>>`<!-- lantern:endif --><!-- lantern:if !git.pr=deploy -->`<<git.base>>`<!-- lantern:endif -->); if that differs from the base branch, put the fix in both afterwards.
3. On that branch, make the card yourself (the commands above, no subagent), tell them to go on from `/l-plan IDEA-NNN`, and **stop here.**
4. Once that is done and merged, `git checkout <this work's branch>` · `git merge <the merged branch>`, then pick up from `## <<section.now>>`.

**When a person changes the order:** if they say so, or `lantern task next` warns `⚠ … task order differs from the last commit`, don't start the next task.
1. Ask why. If it runs into what must finish first, say what the risk is, but the person decides.
2. Once agreed, fix the line order and `[<<attr.after>>:: …]` in `<<file.tasks>>`, note the reason in `<<file.record>>` in one line, run `lantern check` · `lantern report` and commit the documents. Then suggest the next task with `lantern task next`.
3. If not agreed, check with the person and put only the order back.

`[<<attr.after>>:: …]` only takes tasks of this work. Waiting on another work is "Something must come first".

## 2. When to report
- `work`: when the whole work is done · `criterion`: each time an acceptance criterion is complete · `task`: after each task
- **Report and stop right away, whatever the setting:** tests still fail after 3 fixes · you hit a `<<marker.unknown>>` · checking a screen against its mockup · running a migration against a real database · a big change not in the design · something that must come first · an order a person changed
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
<!-- lantern:if !git.pr=work -->
3. Merge the work branch into the base branch and clean up (bring in the base branch → test → merge → clean up). On a conflict, stop and tell the person:
   ```bash
   lantern work finish W-012
   lantern work archive W-012      # work folder → <<folder.archive>>/ (links are fixed too)
   ```
<!-- lantern:endif -->
<!-- lantern:if git.pr=work -->
3. Bring the base branch into the work branch and test; merging is left to the PR. On a conflict, stop and tell the person:
   ```bash
   lantern work finish W-012       # bring in the base branch → test (no merge)
   lantern work archive W-012      # work folder → <<folder.archive>>/ (links are fixed too)
   ```
   After committing the documents, tell the person to run `/l-pr`.
<!-- lantern:endif -->
4. Common wrap-up + drift check + refresh the report:
   ```bash
   lantern close l-build --work W-012
   lantern scan
   lantern report
   ```
5. Final report: evidence summary (tasks · commits · tests · ACs) · what was applied · drift found by `scan` · debt candidates · idea cards left while building · the next task.
