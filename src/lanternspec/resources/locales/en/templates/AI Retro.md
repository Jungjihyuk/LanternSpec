---
id: ${id}
type: report
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: AI Retro
template_version: 1.1.0
based_on: 1.1.0
month: ${month}
---
# 🔁 AI Retro — ${month}

> [!abstract] At a glance
> Each time an automatic loop ends, one line is added for every acceptance criterion (or check) that did not pass on the first try.
> lantern writes the fact fields (time · work · tries · result · run); the AI fills the judgment fields (weakness · remedy · hypothesis · suggestion) with `lantern retro judge`; a person confirms once a week with `lantern retro review`.
> What the AI got stuck on while building (`[stuck:: …]`) is written by the AI with `lantern retro note`, with or without a loop.

## Summary
> [!guide]- 🔁 Update zone — rewritten each time: Summary
> **An overwritten section.** lantern rewrites it with the totals of rows, weaknesses and remedies each time a row is added or confirmed. Don't edit it by hand.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-19 | Default template |
| 1.1.0 | 2026-11-25 | Added the stuck lines (`lantern retro note`) |
