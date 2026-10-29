---
id: CUR-collab
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Collaboration Rules
template_version: 1.0.1
based_on: 1.0.1
---
# 📘 Collaboration Rules

> [!abstract] At a glance
> {{How the team works together, in one sentence (required)}}

## Team
${members_table}

## Branches · review
- One work = one branch (`work/W-012`), base branch: ${base}
- Review: {{Review rules}}

## Commits
- End the commit message with the task ID: `feat: add login button [W-012-T02]`
- One task = one commit (don't mix several tasks in one commit)

## Work units
- Why people changed `/l-plan`'s recommendation is collected in [[${path.unit_log}]]

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-10-29 | Link to the work division rules through a path token, not a written path |
