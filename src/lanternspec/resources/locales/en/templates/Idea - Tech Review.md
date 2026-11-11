---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea - Tech Review
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

## Review summary
> [!guide]- ✍️ How to write — what is looked into and why
> Fill in only what came up in the conversation. Leave unknown cells empty; don't guess.
> Write technology names exactly as they are (so they can be found later).

| Item | Details |
|---|---|
| What to look into | {{Technology · tool · approach name}} |
| What it is for | {{The problem to solve}} |
| Why now | {{What prompted it}} |
| What is used now | {{The current way, or none}} |
| Must-have conditions | {{Without this it can't be used}} |
| Decide by | {{Deadline, or none}} |

## Comparison
> [!guide]- ✍️ How to write — candidates side by side
> One criterion per row, one candidate per column. Keep each cell to a line or two.
> - The current way gets a column too — not changing is also an option.
> - Add a column for each further candidate, and a row for each further criterion that matters to us. Delete rows you don't use.
> - Write only what was checked. For a cell that wasn't checked, write `❓ Needs answer`.

| Criterion | {{Current way}} | {{Candidate A}} | {{Candidate B}} |
|---|---|---|---|
| In one line | {{Intro}} | {{Intro}} | {{Intro}} |
| Version · day checked | {{Version · day}} | {{Version · day}} | {{Version · day}} |
| Pros | {{Pros}} | {{Pros}} | {{Pros}} |
| Cons | {{Cons}} | {{Cons}} | {{Cons}} |
| Meets the must-haves | {{Yes · partly · no}} | {{Yes · partly · no}} | {{Yes · partly · no}} |
| Learning · moving over | {{Easy · medium · hard, and why}} | {{Easy · medium · hard, and why}} | {{Easy · medium · hard, and why}} |
| Cost · license | {{Cost}} | {{Cost}} | {{Cost}} |
| Can it be trusted | {{Who uses it · last update · docs}} | {{Who uses it · last update · docs}} | {{Who uses it · last update · docs}} |
| Biggest risk | {{Risk}} | {{Risk}} | {{Risk}} |

## Conclusion
> [!guide]- ✍️ How to write — filled in after the review
> Leave it empty until the review is done. Technology changes fast, so always write when to look again.
> If the decision will last, record it as a decision record (ADR) and only link it here.

| Item | Details |
|---|---|
| Conclusion | {{One of: use it · try it small · put off · don't use}} |
| What was chosen | {{Candidate name}} |
| Biggest reason | {{One reason}} |
| Accepted downside | {{What we knowingly live with}} |
| Look again when | {{If this changes, review again}} |
| Evidence | {{Links to official docs · release notes · what was tried}} |
| Documents that followed | {{Links to the decision record · work document}} |

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
| 1.0.0 | 2026-11-11 | Tech review idea template (split from Idea; a side-by-side comparison table and a conclusion table) |
