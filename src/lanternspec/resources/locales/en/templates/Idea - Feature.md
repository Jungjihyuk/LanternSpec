---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea - Feature
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

## Feature summary
> [!guide]- ✍️ How to write — only what the conversation gave
> Fill in only what came up in the conversation. Leave unknown cells empty; don't guess.

| Item | Details |
|---|---|
| Who uses it | {{Who}} |
| What they want to do | {{What}} |
| Why it is needed | {{Why}} |
| Information it handles | {{What is entered or stored — what it must have and what is nice to have}} |
| In · out | {{Rough scope}} |

## Details
> [!guide]- ✍️ How to write — what a table cell can't hold
> Write freely what doesn't fit one cell: the flow, examples, a screen you pictured. Delete this section if there is nothing.

{{Details}}

## Result
> [!guide]- ✍️ How to write — filled in after it is built
> Leave it empty until the feature is built. Then fill each cell in a line or two.
> Don't leave out what changed from the first idea — read together, feature cards should show what was added and how.

| Item | Details |
|---|---|
| What was built | {{The feature that actually exists}} |
| What changed from the first idea | {{What changed, and why}} |
| What was left out | {{What didn't go in this round, and why}} |
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
| 1.0.0 | 2026-11-11 | Feature idea template (split from Idea, with a feature summary table) |
| 1.1.0 | 2026-11-11 | Added a result table filled in after it is built, dropped the feature name row that repeats the heading, and merged the two data rows into one |
