---
id: ${id}
type: debt
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Competency Card
template_version: 1.0.0
based_on: 1.0.0
area: ${area}
aliases: ${aliases}
owner: ${owner}
ask_count: 0
from: ${source}
work: []
resolved: ""
---
# 🛠 ${id} ${name}

> [!abstract] At a glance
> {{What you should be able to build yourself, in one line (required)}}

## Source
> [!guide] Written by the skills. This competency debt started from "shall I build it myself?" after the understanding debt was resolved.

- ${today} came from understanding debt ${source_link}

## Practice tasks
> [!guide] 🟦 Source section · 1–3 small tasks you can finish. Make them checkable ("understand JWT" ✕ → "build token issue · verify · refresh APIs myself" ○).

- [ ] {{Practice task (required)}}

## What I Built
> [!guide] `lantern debt practice` adds a line each time (date · link to the result · a one-line takeaway). When the tasks are done, `lantern debt resolve`.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
