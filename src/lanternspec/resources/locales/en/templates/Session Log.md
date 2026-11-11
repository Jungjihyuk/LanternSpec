---
id: ${id}
type: session
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Session Log
template_version: 1.0.3
based_on: 1.0.3
---
# 🕐 ${today} Session Log

> [!abstract] At a glance
> When eligible works have no log document, this saves progress read from their documents just before conversation compaction.
> lantern writes it automatically: one file per date in the base folder, or per date and work ID in parallel worktrees.

## Now
> [!guide]- 🔁 Updated section — rewritten each time: Now
> **Overwritten each time.** Each time right before the AI summarizes the conversation, lantern rewrites it with where things stand.

## History
> [!guide]- 🔁 Updated section — added below: earlier 'Now'
> Each time 'Now' is rewritten, what was there moves down here with its time.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
| 1.0.2 | 2026-11-09 | Clarify the save condition and separate fallback files by parallel work |
| 1.0.3 | 2026-11-11 | Notes folded, under titles that say what they are |
