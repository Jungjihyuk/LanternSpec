---
id: ${id}
type: adr
status: ${adr_status.proposed}
created: ${today}
updated: ${today}
links: ${links}
template: ADR
template_version: 1.0.2
based_on: 1.0.2
superseded_by: ""
---
# 📝 ${id} ${name}

> [!abstract] At a glance
> {{The decision in one line (required)}}

## Context
> [!guide]- ✍️ How to write — what to decide, and why now
> What had to be decided, and why now. A decision worth recording is one where, six months later, someone might ask "why did we do this?"

{{Context (required)}}

## Options considered
> [!guide]- ✍️ How to write — pros and cons of each option
> The pros and cons of each option. Keep the options not chosen too.

| Option | Pros | Cons |
|---|---|---|
| {{Option A (required)}} | {{Pros}} | {{Cons}} |
| {{Option B}} | {{Pros}} | {{Cons}} |

## Decision
> [!guide]- ✍️ How to write — what was chosen and why
> What was chosen, the biggest reason for it, and who decided when.

{{Decision (required)}}

## Consequences
> [!guide]- ✍️ How to write — what gets easier or harder
> What this decision makes easier, what it makes harder, and which documents must change with it.

{{Consequences}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
| 1.0.2 | 2026-11-11 | Notes folded, under titles that say what they are |
