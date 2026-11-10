---
name: l-task
description: Break a design into an ordered task list — read a work's (W-NNN) <<file.plan>> · <<file.design>> and write <<file.tasks>> in W-NNN-T01 form, each task with a size · the acceptance criteria it serves · the tasks that must finish first. Use after /l-design is approved, before /l-build.
invocation: model
argument-hint: "W-NNN"
---

# /l-task — break it into tasks

**Purpose:** turn the design into an **ordered task list**. `/l-report` reads this list to draw the kanban and timeline.

Input: `$ARGUMENTS` — `W-012`.

## 0. Before starting
- Check that `<<file.design>>` is approved (frontmatter `approved`). If it is empty<!-- lantern:if design.approval=off --> (design.approval is off, so there is no gate), go ahead.<!-- lantern:endif --><!-- lantern:if !design.approval=off -->, stop and suggest going through the approval gate of `/l-design W-012` first.<!-- lantern:endif -->
- Read the acceptance criteria (AC) in `<<file.plan>>` and `<<file.design>>`.
- Read `docs/<<folder.rules>>/<<file.task_rules>>` — the rules for sizes, where an unknown goes and spike tasks. If it isn't there, `lantern template show "<<file.task_rules>>"`.

## 1. Make the task list
```bash
lantern scaffold doc W-012 "<<doc.tasks>>"
```
Then add tasks one by one **in the order they are best worked on** (the script numbers them):
```bash
lantern task add W-012 "<what>" --size <<size.xs>>|<<size.s>>|<<size.m>>|<<size.l>> --ac AC-1 [--after T01] [--spike] [--screen "<screen name>"]<!-- lantern:if team --> --owner "<owner>"<!-- lantern:endif -->
```
- **Order:** what must finish first → data · foundations → features → screens → wrap-up. In units that can be checked at once.
- Decide the **size** by the size table in the rules document — the time a person would take, working without interruption. Split anything that looks bigger than `<<size.l>>`; when unsure, pick the larger size.
- **Don't add planned dates.** Only when the person gives dates: `--start-plan 2026-11-01 --due-plan 2026-11-03`.
- Don't write long descriptions; link the relevant part of `<<file.design>>`.
- Tasks that **can run alongside** others (different files, nothing to wait for) get `--parallel` (marked `[P]` — parallel agents can take them together).
- **Put each unknown where the rules document's "Where an unknown goes" table says.** A choice that can be settled by weighing it up goes back to design (`/l-design`) instead of becoming a task. What can only be learned by trying becomes a spike task: `--spike` (`<<marker.spike>>` before the title — its size is a time limit; tasks that depend on its conclusion go after it with `--after`). A task with something only a person can answer gets `--unknown` (`<<marker.unknown>>` at the end of the line) — `/l-build` skips it.
- Screen tasks get `--screen`<!-- lantern:if plan.ui_reference=required --> (`/l-build` won't start them without a mockup)<!-- lantern:endif -->. Write a screen task as **building** something. Don't make "look at the screen" a task of its own — `/l-build` checks the screen when a screen task is done.
- When `lantern ref domain --work W-012` lists domain knowledge, tie each section to the tasks that use it: `lantern ref attach "<address>" --work W-012 --task "T02 T03"` (all of them at once — attaching again replaces the line).

## 2. Review
- Does **every acceptance criterion have at least one task**? (`lantern check` reports missing ACs)
- When a task **falls outside the purpose in the work's name**, take it out and suggest **divide and place** with `/l-plan` (one work = one purpose)
- Check the order and what is blocked with `lantern task list W-012`
- If the person wants planned dates, only **suggest** them from the actual average per size: `lantern task estimate W-012 [--from 2026-11-01]` → if they agree, `--apply`

## 3. Wrap up
Write the number of tasks and the overall flow in one line in "<<marker.glance>>", and move the stage up:
```bash
lantern work stage W-012 "<<work_status.tasks>>"
lantern close l-task --work W-012 --commit
```
**Next:** `/l-build W-012`.
