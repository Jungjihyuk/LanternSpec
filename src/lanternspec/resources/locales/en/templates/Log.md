---
id: ${work_id}
type: record
status: ${work_status.build}
created: ${today}
updated: ${today}
links: ${links}
template: Log
template_version: 1.0.0
based_on: 1.0.0
---
# 🔨 ${work_id} ${name} — Log

> [!abstract] At a glance
> {{At a glance (required)}}

## Now
> [!guide] **Overwritten each time.** Only the task in progress · the next task · what is blocked · open questions, in 3–5 lines. Don't paste the conversation.

- Progress: {{In progress}}
- Next: {{Next task}}

## Evidence
> [!guide] 🟦 Source section · One block per task: what changed · commit · test results · whether the acceptance criteria pass · (UI) capture path. Write **what can be checked**, not "it's done".

| Task | Commit | Files changed | Tests | Acceptance criteria |
|---|---|---|---|---|

## Schema Changes
> [!guide] Only when the schema changed. Date · what changed · why (ADR link) · migration file.

| Date | Change | Why | Migration |
|---|---|---|---|

## Decisions · failed attempts
> [!guide] Small library choices get one line here. Hard-to-reverse decisions get an `/l-adr` link.

## History
> [!guide] What was pushed out of "Now" piles up below, with its date.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
