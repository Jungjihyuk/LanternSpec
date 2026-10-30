---
name: l-resume
description: Carry on an earlier conversation — whichever AI tool it was in (Claude Code · Codex · Antigravity), whether it was cut off or finished, read where it stopped (the last requests · the AI's last words · changed files · uncommitted changes · work in progress), confirm, then continue. Use when the user asks to continue earlier work, or a previous session was cut off (usage limit, crash) or happened in another AI tool.
invocation: model
argument-hint: "[conversation number]"
---

# /l-resume — carry on an earlier conversation

**Purpose:** find where the earlier conversation stopped and continue in the same direction. Nobody needs to know where the transcript files are — the hooks note them for every conversation, and `lantern resume` reads them.

Input: `$ARGUMENTS` — empty for the latest conversation, or a number from the list.

## 1. Read where it stopped
```bash
lantern resume                 # recent conversations + the tail of the latest one
lantern resume --session 2     # another conversation
lantern resume --more 1        # earlier messages (only when needed — it saves context)
```
- **⚠ cut off** means the last turn never finished; what it was doing may be half done.
- If the transcript can't be read, its last lines are shown as they are — decide from those and step 2.

## 2. Check against the current state
- See whether the **uncommitted changes** in the summary match the last request. For a cut-off conversation, open half-changed files with `git diff` to see how far it got.
- With **work in progress**, check how far it got in that work's `<<file.record>>` "<<section.now>>" section and in `<<file.tasks>>`.
- When the summary and the documents disagree, **the documents and code win** (the conversation may have been cut).

## 3. Confirm, then continue
Ask in one line: **"I'll carry on from here: <what · from where>. Right?"**
- If yes, continue. If work was in progress, hand over to that stage's skill (e.g. `/l-build W-012` while building).
- If no, start from where the person says.
- Before **running again** what the cut-off turn was doing, check whether its result is already there (files · commits · documents) — never do the same work twice.

## 4. Wrap up
If it ends here instead of handing over to another skill, leave only the run record (no documents changed, so no check or map update):
```bash
lantern close l-resume --no-check --no-map
```
