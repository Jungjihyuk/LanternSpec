---
id: ${id}
type: idea
kind: ${kind}
status: ${status}
created: ${today}
updated: ${today}
links: ${links}
template: Idea - Bug
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

## Bug summary
> [!guide]- ✍️ How to write — only what was seen, no guesses
> Write only what was seen. Don't guess the cause here (it goes in 'Cause and fix' below, after the fix).
> Leave unknown cells empty; don't guess.

| Item | Details |
|---|---|
| Where | {{Screen · feature · command name}} |
| What happens | {{What was actually seen}} |
| What should happen | {{What was expected}} |
| Error text | {{The text on screen or in the log, as it is}} |
| How often | {{One of: every run · sometimes · only once}} |
| How bad | {{One of: unusable · big nuisance · small nuisance · only looks wrong}} |
| Environment | {{Device · operating system · browser · version}} |
| Since when | {{The day first seen, and what changed around then}} |
| Workaround | {{If there is one}} |

## Steps to reproduce
> [!guide]- ✍️ How to write — following them shows the same problem
> One action per line, so that someone new gets the same problem by following them.
> If it couldn't be reproduced, write the last situation it was seen in and leave `❓ Needs answer: steps to reproduce`.

1. {{First action}}
2. {{Next action}}
3. {{The moment the problem shows}}

## Cause and fix
> [!guide]- ✍️ How to write — filled in after the fix
> Leave it empty until the bug is fixed. Then fill each cell in a line or two.
> This is the table someone reads first when the same bug comes back — write it so the cause and the fix are clear from this table alone.

| Item | Details |
|---|---|
| Bug type | {{One of: display · wrong behavior · data · performance · crash or hang · integration · security · configuration · environment}} |
| Root cause | {{Why it happened}} |
| Where the cause was | {{File · function · setting name}} |
| Suspected but ruled out | {{What was looked at first, and why it wasn't it}} |
| How it was fixed | {{What changed}} |
| How the fix was checked | {{Tests · what was tried by hand}} |
| What keeps it from coming back | {{Added tests · checks · rules}} |
| Work that fixed it | {{Link to the work document or commit}} |
| Words to find it again | {{A piece of the error text · words for the symptom}} |

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
| 1.0.0 | 2026-11-11 | Bug idea template (split from Idea; what was seen, steps to reproduce, and cause and fix kept apart) |
