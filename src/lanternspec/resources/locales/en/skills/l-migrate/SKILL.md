---
name: l-migrate
description: Bring another tool's documents over to our way — moves OpenSpec changes (openspec/changes) into works in <<folder.archive>> when finished, works in <<folder.works>> when in progress, and ideas in <<folder.ideas>> when not yet decided. The sections of proposal · design · tasks go into the matching sections of <<file.plan>> · <<file.design>> · <<file.tasks>>; content with no matching section is gathered, not deleted. The originals are kept in <<folder.legacy>>. Use when an existing project has an openspec/ folder and the user wants its changes as LanternSpec works and ideas.
invocation: model
argument-hint: "openspec"
---

# /l-migrate — another tool's documents, our way

**Purpose:** move documents of another tool that follow one format into LanternSpec's folders and templates, so past and ongoing work continue in one place.
For now it moves OpenSpec. Documents without a consistent format are not moved; they stay in `<<folder.legacy>>/`.

## Rules
- `lantern migrate openspec` does the conversion. You don't rewrite the documents — the content must not change.
- The originals are kept in `<<folder.legacy>>/openspec/` and are not edited.
- The command suggests where each change goes; the person confirms the open ones.

## Steps
1. Show the preview (nothing changes):
   ```bash
   lantern migrate openspec
   ```
   - Archived changes (`changes/archive/`) become `<<folder.archive>>/W-NNN …`, in date order.
   - An open change is suggested for the archive when all its tasks are done, for `<<folder.works>>/W-NNN …` when it has a design or tasks, and for `<<folder.ideas>>/` when it is only a note.
   - The capabilities under `specs/` each add one row to `<<folder.current>>/<<file.features>>`.
2. **Have the person confirm where the open changes go.** Show the list and ask only about what should change. Pass the changes as options (each can be repeated):
   ```bash
   lantern migrate openspec --idea "<change name>" --work "<change name>" --archive "<change name>"
   ```
3. Once approved, move them. If it stops because the documents have uncommitted changes, suggest committing first:
   ```bash
   lantern migrate openspec --apply
   ```
   In a repository git tracks, it leaves one commit, and one `git revert` undoes it.
4. Check the result:
   ```bash
   lantern check
   ```
   - Archived works should have no warnings.
   - Works in progress keep "has no size" · "No task is linked" warnings, because OpenSpec tasks carry no size and no link to an acceptance criterion. Say that `/l-task` fills them in when that work is picked up. Don't fill them all in now.
5. Point out what the person should look at in the moved documents:
   - `## <<marker.migrate_bin>>` at the bottom — content gathered because it had no matching section (OpenSpec's Capabilities · Impact · Risks …). Move what is needed into the right section; the rest can be deleted.
   - "Hard-to-reverse choices" in `<<file.design>>` — left empty. Read the design and, if there was a hard-to-reverse decision, suggest recording it with `/l-adr`.
6. Leave the other documents in `<<folder.legacy>>/` as they are. When the person has read them and names one to move, move it then with `/l-template migrate "<<folder.legacy>>/<document>.md"`, one at a time.
7. If the preview listed "OpenSpec instructions · commands remain in", show that list. Don't delete them — whether to keep using them is the person's call.

## Common finish
```bash
lantern close l-migrate [--commit]
```
