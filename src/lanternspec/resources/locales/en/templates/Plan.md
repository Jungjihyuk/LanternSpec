---
id: ${work_id}
type: plan
status: ${work_status.plan}
created: ${today}
updated: ${today}
links: ${links}
template: Plan
template_version: 1.1.1
based_on: 1.1.1
domain: "{{Domain}}"
ui: false
owner: ${owner}
---
# 📋 ${work_id} ${name} — Plan

> [!abstract] At a glance
> {{What this work does and why, in one sentence (required)}}

## What
> [!guide] What appears, described by **what the user sees**, in 2–3 sentences. How it is built goes in the design.

{{What (required)}}

## Why
> [!guide] Why this work is needed. If it started from an idea, link that idea.

{{Why (required)}}

## User scenario
> [!guide] The steps a user goes through to use this feature, as a numbered list in order.

1. {{Scenario (required)}}

## Acceptance criteria
<!-- lantern:if ac_format=gwt -->
> [!guide] The criteria for deciding this work is done. One per line:
> `- [ ] AC-1 Given: … · When: … · Then: …` (Given only when needed)
> - Make the result checkable: "within 2 seconds", not "fast"
> - `lantern check --epic` checks the format

- [ ] AC-1 Given: {{Given}} · When: {{When (required)}} · Then: {{Then (required)}}
<!-- lantern:endif -->
<!-- lantern:if ac_format=simple -->
> [!guide] One per line: `- [ ] AC-1 When …, then …`
> - Make the result checkable: "within 2 seconds", not "fast"
> - `lantern check --epic` checks the format

- [ ] AC-1 {{Acceptance criterion (required)}}
<!-- lantern:endif -->

## Out of scope
> [!guide] What this work **does not** do. If it should happen later, keep it as an idea (`/l-idea`).

- {{Out of scope}}

## Domain Knowledge Used
> [!guide] ⚙️ Links to the sections of domain knowledge (laws · policies · business rules) this work needs. `/l-plan` and `/l-task` fill it with `lantern ref attach`.
> - One section per line. The tasks that use it are added at the end of the line
> - Material outside the project isn't written here (it stays only in this computer's `.lantern/`)
> - Leave it empty when nothing applies

## Needs answer
> [!guide] Don't guess what you don't know; write `- ❓ Needs answer: question`.
> Once answered, write the answer in the right section and delete this line.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.1.0 | 2026-11-01 | Added the "Domain Knowledge Used" section |
| 1.1.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
