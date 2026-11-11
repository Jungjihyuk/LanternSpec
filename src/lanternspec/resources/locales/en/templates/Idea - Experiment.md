---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea - Experiment
template_version: 1.0.0
based_on: 1.0.0
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

## Experiment summary
> [!guide]- ✍️ How to write — what is set before trying
> Write the expectation and the success bar **before trying** (written afterwards, the bar follows the result).
> Fill in only what came up in the conversation. Leave unknown cells empty; don't guess.

| Item | Details |
|---|---|
| What we want to know | {{The question in one line}} |
| Expectation | {{What will probably happen}} |
| Why it matters | {{The decision that depends on the result}} |
| How to try it | {{The smallest way to try}} |
| What to measure | {{A number, or what to check by eye}} |
| Success bar | {{This much means the expectation held}} |
| Budget | {{The limit on hours and cost}} |
| In · out | {{Rough scope}} |

## Result
> [!guide]- ✍️ How to write — filled in after trying
> Leave it empty until the experiment is done. Keep experiments whose expectation was wrong too — the record saves running the same one again.

| Item | Details |
|---|---|
| Verdict | {{One of: as expected · not as expected · inconclusive}} |
| What happened | {{Measured values · what was seen}} |
| What we learned | {{A fact that holds next time too}} |
| Next step | {{One of: adopted · more experiments · stopped — and why}} |
| Work that followed | {{Link to the work document}} |

## Details
> [!guide]- ✍️ How to write — what a table cell can't hold
> Write what doesn't fit one cell: the steps taken, a table of measurements, where it got stuck. Delete this section if there is nothing.

{{Details}}

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
| 1.0.0 | 2026-11-11 | Experiment idea template (split from Idea; a summary table set beforehand and a result table for afterwards) |
