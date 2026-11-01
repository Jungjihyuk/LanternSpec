---
id: ${id}
type: session
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Session Log
template_version: 1.0.1
based_on: 1.0.1
---
# 🕐 ${today} Session Log

> [!abstract] At a glance
> When no work is in progress, this keeps where things stood right before the AI summarized a long conversation.
> lantern writes it automatically, one file per day.

## Now
> [!guide] **Overwritten each time.** Each time right before the AI summarizes the conversation, lantern rewrites it with where things stand.

## History
> [!guide] Each time 'Now' is rewritten, what was there moves down here with its time.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
