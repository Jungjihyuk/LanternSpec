---
id: ${id}
type: debt
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Debt Card
template_version: 1.0.1
based_on: 1.0.1
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
> [!guide] Filled in automatically. One line each time you ask about this: date · work · what you were doing when you asked.

- ${today} ${work_text}

## What I understand now
> [!guide] What you understand now, in your own words. If there is a note in the knowledge store, link it instead of copying it.
> (When `learn.verify` in `lantern.yaml` is `explain`, the one-line explanation `/l-learn` took from you goes here.)

{{What I understand now}}

## Review · study suggestions
> [!guide] How to learn this again.
> - If ${debt_status.asked_again.label}: a link to your note and the parts to look at again
> - If ${debt_status.new.label}: where the draft of a new learning note is

{{Review · study suggestions}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
