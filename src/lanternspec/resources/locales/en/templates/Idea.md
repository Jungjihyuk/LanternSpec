---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea
template_version: 1.0.0
based_on: 1.0.0
auto: ${auto}
dropped_reason: ""
---
# 💡 ${id} ${name}

> [!abstract] At a glance
> {{One-line summary (required)}}

## Original Words
> [!guide] 🟦 Source section · Copy what the user said **without changing it**. When more is added later, stack it below with the date in front.

${raw}

## Why it helps
> [!guide] 🟦 Source section · Who it helps and how, in 1–3 lines. If you don't know, `❓ Needs answer`.

{{Why it helps}}

## Related documents
> [!guide] 🔗 Linking section · Only link related ideas, works and current-state documents (don't copy their content).

{{Related documents}}

## Status Log
> [!guide] Written by the skills. ${idea_status.dropped.label} needs a one-line reason (`dropped_reason`).

- ${today} recorded as ${idea_status.new.label}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
