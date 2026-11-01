---
id: ${id}
type: debt
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Competency Card
template_version: 1.0.1
based_on: 1.0.1
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
> [!guide] Filled in automatically. This card exists because, after the understanding debt was resolved, you said yes to "shall I build it myself?".

- ${today} came from understanding debt ${source_link}

## Practice tasks
> [!guide] 1–3 small tasks you can finish. Write them so you can tell whether they are done.
> - Bad: "understand JWT"
> - Good: "build the token issue · verify · refresh APIs myself"

- [ ] {{Practice task (required)}}

## What I Built
> [!guide] `lantern debt practice` adds one line at a time: date · link to the result · a one-line takeaway.
> When all the tasks are done, close this card with `lantern debt resolve`.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
