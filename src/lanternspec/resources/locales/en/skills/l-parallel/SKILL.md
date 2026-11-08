---
name: l-parallel
description: Check before parallel work — before starting several works (W-NNN) at once in worktrees, find what they must decide together (authentication · shared data · API format · shared screen rules · outside services) and how they depend on each other, have a person decide, record it as decision records (ADR), then start them. Use before starting two or more works in parallel.
invocation: manual
argument-hint: "W-NNN W-NNN …"
---

# /l-parallel — check before parallel work

**Purpose:** before starting several works at once, settle what they must decide together, so merging doesn't mean redoing work.
When works build the same thing differently (say JWT in one, sessions in the other), they merge without a conflict and the problem surfaces later.

Input: `$ARGUMENTS` — the works to start together (`W-001 W-002`). Works already running in worktrees are looked at too.

## 0. Prepare
- Read each work's `<<file.plan>>` and `<<file.design>>`. For a work without a design, say "The check is more accurate after the design," and ask whether to go on from the plan alone.
- See the shared places and the linked decision records:
  ```bash
  lantern work overlap W-001 W-002     # same files · tables, and each work's linked decision records
  ```
- Read the decisions already made (`<<adr_status.accepted>>`) in `<<folder.decisions>>/`. Don't ask again about what's already decided.

## 1. Find what to decide together
Find what two or more works need but neither a design nor a decision record settles:
- Authentication · authorization (e.g. JWT / sessions)
- Shared data (the same tables, tables that refer to each other)
- API format (response · error shape, address rules)
- Shared screen parts · design rules
- Outside services · major libraries

Also find where one work depends on another's result (e.g. the profile depends on the sign-in's authentication).

## 2. Have a person decide (one at a time)
For each item, show **what · why it must be decided together · the recommendation and why · the choices**. The recommendation is your judgment, so always give the reason.

Where works depend on each other, let the person choose:
- Decide just that first and run them in parallel (recommended when the decision is clear)
- Finish the earlier work first and go in order

Record each decision with `/l-adr`. For each related work, add its ID to `adr` in the `<<file.design>>` frontmatter and reflect it in the design text. Commit the changed documents before starting (a worktree only gets committed documents).

## 3. Start
```bash
lantern work start W-001 W-002 --skip-check
```
- If there was nothing to decide together, say "Nothing needs deciding together" and start right away.
- If going in order leaves only one work to start now, don't make a worktree (don't run `lantern work start`). Give the order: "Run `/l-build W-001` in the base folder. When it's done, `/l-build W-002`."
- If two or more works are left to start together, start only those with `lantern work start`, and note each postponed work in the final report as "W-00N after W-00M is merged".
- Show the way to open each work exactly as the command gives it (one line per terminal).

## Common wrap-up
```bash
lantern close l-parallel
```
**Next:** if the works started together, run `/l-build` in each terminal with the command given, and `/l-finish` in the base folder when all are done. If they go in order, run `/l-build` in the base folder in the order given above.
