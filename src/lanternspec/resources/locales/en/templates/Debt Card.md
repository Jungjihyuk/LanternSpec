---
id: ${id}
type: debt
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Debt Card
template_version: 1.0.0
based_on: 1.0.0
area: ${area}
aliases: ${aliases}
owner: ${owner}
ask_count: 1
note: ${note}
work: ${work}
last_asked: ${today}
last_session: ${session}
resolved: ""
---
# 📒 ${id} ${name}

> [!abstract] At a glance
> {{What this technology is and why it is used, in one line (required)}}

## Where It Came Up
> [!guide] Written by the skills. One line per ask: date · work · context.

- ${today} ${work_text}

## What I understand now
> [!guide] Written by the person (or, with `learn.verify: explain`, the user's one-line explanation). If there is a note in the knowledge store, link it instead of copying it.

{{What I understand now}}

## Review · study suggestions
> [!guide] ${debt_status.asked_again.label} → note link and what to review / ${debt_status.new.label} → path of the learning-note draft.

{{Review · study suggestions}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
