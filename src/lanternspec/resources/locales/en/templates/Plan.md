---
id: ${work_id}
type: plan
status: ${work_status.plan}
created: ${today}
updated: ${today}
links: ${links}
template: Plan
template_version: 1.1.0
based_on: 1.1.0
domain: "{{Domain}}"
ui: false
owner: ${owner}
---
# 📋 ${work_id} ${name} — Plan

> [!abstract] At a glance
> {{At a glance (required)}}

## What
> [!guide] 🟦 Source section · What you are building, in 2–3 sentences, described by **what the user sees**.

{{What (required)}}

## Why
> [!guide] 🟦 Source section · Why this work is needed. Link the idea it started from, if any.

{{Why (required)}}

## User scenario
> [!guide] 🟦 Source section · The flow the user actually goes through, as a numbered list.

1. {{Scenario (required)}}

## Acceptance criteria
<!-- lantern:if ac_format=gwt -->
> [!guide] 🟦 Source section · One per line: `- [ ] AC-1 Given: … · When: … · Then: …` (Given only when needed). Make the result **checkable** ("fast" ✕ → "within 2 seconds" ○). `lantern check --epic` checks them.

- [ ] AC-1 Given: {{Given}} · When: {{When (required)}} · Then: {{Then (required)}}
<!-- lantern:endif -->
<!-- lantern:if ac_format=simple -->
> [!guide] 🟦 Source section · One per line: `- [ ] AC-1 When …, then …`. Make the result **checkable** ("fast" ✕ → "within 2 seconds" ○). `lantern check --epic` checks them.

- [ ] AC-1 {{Acceptance criterion (required)}}
<!-- lantern:endif -->

## Out of scope
> [!guide] 🟦 Source section · What this work **does not** do. If it should happen later, keep it as an idea.

- {{Out of scope}}

## Domain Knowledge Used
> [!guide] /l-plan fills this with `lantern ref attach`. One line = one section of domain knowledge — which tasks use it. Material outside the project isn't written here (it is kept in this computer's `.lantern/`). Leave it empty when nothing applies.

## Needs answer
> [!guide] Don't guess what you don't know; write `- ❓ Needs answer: question`. Once answered, put it in the right section and delete the line.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.1.0 | 2026-11-01 | Added the "Domain Knowledge Used" section |
