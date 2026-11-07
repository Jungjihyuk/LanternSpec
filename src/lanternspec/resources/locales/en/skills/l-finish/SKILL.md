---
name: l-finish
description: Wrap up parallel works — merge the works finished in worktrees into the base branch one by one from the base folder (bring in the base branch → test → merge → clean up), then, once all pass, update the current state, archive and report in one go. Run it from the base folder in a single session. Use after parallel works finish in their worktrees.
invocation: manual
argument-hint: "[W-NNN …]"
---

# /l-finish — wrap up parallel works

**Purpose:** merge the works finished in worktrees into the base branch one by one, and once all pass, bring the current-state documents up to date in one go.
Only this skill changes the documents several works share (current state · archive · report), so run it **from the base folder, in a single session**.

Input: `$ARGUMENTS` — the works to merge (`W-001 W-002`). Without it, let the person choose.
Current settings: current-state update `<<build.merge_approval>>`<!-- lantern:if build.test --> · tests `<<build.test>>`<!-- lantern:endif -->

## 0. Before starting
- Check that this runs in the base folder. Inside a worktree, stop and say to run it again from the base folder.
- If `git status` shows uncommitted changes, stop and say: "The base folder has uncommitted changes. Another wrap-up may be in progress."
- Show the works "waiting for /l-finish" from `lantern work list`, and let the person choose which to merge now and in what order (only those given as arguments, if any).

<!-- lantern:if !git.pr=work -->
## 1. Merge one at a time (in the chosen order)
```bash
lantern work finish W-001     # bring in the base branch → test → merge → clean up the worktree
```
- On a conflict, follow **On a conflict** in `/l-build` inside that work's folder (the worktree it names), then run it again. Conflicts only in generated documents resolve themselves.
- If the tests fail, leave that work unmerged and ask the person whether to go on to the next work.
- If the session can't delete a worktree folder, don't delete it another way; put the terminal command it gives in the final report.
<!-- lantern:endif -->
<!-- lantern:if git.pr=work -->
## 1. Bring each up to date (in the chosen order)
A PR does the merging. For each work, bring in the base branch and test:
```bash
lantern work finish W-001     # bring in the base branch → test (no merge)
```
- On a conflict, follow **On a conflict** in `/l-build` inside that work's folder, then run it again.
- Do steps 2 · 3 below **for each work, in that work's folder**, commit them on its branch, then point the person to `/l-pr`.
<!-- lantern:endif -->

## 2. Update the current state (every merged work)
- For each work, read `<<file.design>>` and `<<file.record>>`, and show a one-page summary following **When everything is done — apply to the current state** in `/l-build`.
- When several works change the same document (e.g. `<<file.features>>`), show it on one page. Don't delete lines another work wrote.
- The approval rules are the same as `/l-build`. **Always ask about data structure · API changes, whatever the setting.**

## 3. Archive · report
```bash
lantern work archive W-001    # for each merged work
lantern close l-finish
lantern scan
lantern report
```
Commit the documents in one go (list every merged work ID in the commit message).

## 4. Final report
Works merged · works left and why · what was updated · drift found by `scan` · any `⚠` from `finish` · worktrees a person must delete in a terminal.
