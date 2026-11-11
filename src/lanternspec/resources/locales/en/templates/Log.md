---
id: ${work_id}
type: record
status: ${work_status.build}
created: ${today}
updated: ${today}
links: ${links}
template: Log
template_version: 1.0.2
based_on: 1.0.2
---
# 🔨 ${work_id} ${name} — Log

> [!abstract] At a glance
> {{How far the work has come, in one sentence (required)}}

## Now
> [!guide]- 🔁 Updated section — rewritten each time: now · next · blocked
> **Overwritten each time.** Only what you are doing · the next task · what is blocked · questions waiting for an answer, in 3–5 lines. Don't paste the conversation.

- Progress: {{In progress}}
- Next: {{Next task}}

## Evidence
> [!guide]- ✍️ How to write — evidence someone can check
> One table row per task. Instead of "it's done", write **what someone else can check**.
> - Commit · changed files · test results · whether the acceptance criteria pass
> - If a screen changed, the capture file path too

| Task | Commit | Files changed | Tests | Acceptance criteria |
|---|---|---|---|---|

## Schema Changes
> [!guide]- ✍️ How to write — only when the schema changed
> Only when the database structure (schema) changed. If there is a decision record (ADR), link it in the 'Why' column.

| Date | Change | Why | Migration |
|---|---|---|---|

## Decisions · failed attempts
> [!guide]- ✍️ How to write — choices made · approaches dropped
> One line for each choice made and each approach tried and dropped while working. Small decisions such as a library go here; hard-to-reverse decisions get recorded with `/l-adr` and only linked here.

## History
> [!guide]- 🔁 Updated section — added below: earlier 'Now'
> Each time 'Now' is rewritten, what was there moves down here with its date.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
| 1.0.2 | 2026-11-11 | Notes folded, under titles that say what they are |
