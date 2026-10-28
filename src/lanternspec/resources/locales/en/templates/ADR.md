---
id: ${id}
type: adr
status: ${adr_status.proposed}
created: ${today}
updated: ${today}
links: ${links}
template: ADR
template_version: 1.0.0
based_on: 1.0.0
superseded_by: ""
---
# 📝 ${id} ${name}

> [!abstract] At a glance
> {{The decision in one line (required)}}

## Context
> [!guide] 🟦 Source section · What had to be decided, and why now. Check question: "in six months, will someone ask 'why did we do this?'"

{{Context (required)}}

## Options considered
> [!guide] 🟦 Source section · Pros and cons of each option. Keep the ones not chosen too.

| Option | Pros | Cons |
|---|---|---|
| {{Option A (required)}} | {{Pros}} | {{Cons}} |
| {{Option B}} | {{Pros}} | {{Cons}} |

## Decision
> [!guide] 🟦 Source section · What was chosen and the deciding reason. Who decided, and when.

{{Decision (required)}}

## Consequences
> [!guide] 🟦 Source section · What gets easier · what gets harder · which documents change.

{{Consequences}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
