---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea - Improvement
template_version: 1.1.0
based_on: 1.1.0
auto: ${auto}
dropped_reason: ""
blocked_reason: ""
revisit_when: ""
---
# 💡 ${id} ${name}

> [!abstract] At a glance
> {{One-line summary (required)}}

## Original Words
> [!guide]- ✍️ How to write — word for word
> Copy what the user said **without changing it**.
> When more is said about the same idea, stack it below with the date in front.

${raw}

## Improvement summary
> [!guide]- ✍️ How to write — only what the conversation gave
> Fill in only what came up in the conversation. Leave unknown cells empty; don't guess.

| Item | Details |
|---|---|
| What to improve | {{Screen · feature · flow name}} |
| How it is now | {{What it does now}} |
| What is inconvenient | {{The inconvenience}} |
| How it should be | {{What would be better}} |
| Who runs into it | {{Who}} |
| How often | {{One of: every run · sometimes · only in certain cases}} |
| How people get by now | {{The workaround in use, or none}} |
| In · out | {{Rough scope}} |

## Details
> [!guide]- ✍️ How to write — what a table cell can't hold
> Write what doesn't fit one cell: the steps where it got in the way, examples, other products you compared. Delete this section if there is nothing.

{{Details}}

## Improvement result
> [!guide]- ✍️ How to write — filled in after the change
> Leave it empty until the improvement is made. Then fill each cell in a line or two.
> Keep what was tried and didn't work too — the record saves the next person from going the same way.

| Item | Details |
|---|---|
| What changed | {{What was actually changed}} |
| Before and after | {{How it was, and how it is now}} |
| Tried but didn't work | {{What was tried, and why it didn't work}} |
| What is still left | {{What is still inconvenient, or none}} |
| Work that followed | {{Link to the work document}} |

## Related documents
> [!guide]- ✍️ How to write — links only
> 🔗 Only link related ideas, works and current-state documents.
> Don't copy their content.

{{Related documents}}

## Status Log
> [!guide]- ⚙️ Generated section — each time the status changes
> Filled in automatically. Changing it to ${idea_status.dropped.label} needs a one-line reason (the `dropped_reason` property at the top).
> ${idea_status.blocked.label} means wanted, but not possible now. It needs why (`blocked_reason`) and what would reopen it (`revisit_when`).

- ${today} recorded as ${idea_status.new.label}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-11 | Improvement idea template (split from Idea, with a summary table of how it is now and how it should be) |
| 1.1.0 | 2026-11-11 | Added an improvement result table filled in after the change and a 'How people get by now' row, and made 'How often' a fixed choice |
