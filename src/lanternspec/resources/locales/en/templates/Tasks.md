---
id: ${work_id}
type: tasks
status: ${work_status.tasks}
created: ${today}
updated: ${today}
links: ${links}
template: Tasks
template_version: 1.0.1
based_on: 1.0.1
---
# ✅ ${work_id} ${name} — Tasks

> [!abstract] At a glance
> {{At a glance (required)}}

> [!guide] One task per line. Format:
> `- [ ] W-012-T02 What [size:: M] [ac:: AC-1] [after:: T01]`<!-- lantern:if team --> `[owner:: name]`<!-- lantern:endif -->
> - Order them **the way they are best worked on**: what must finish first → data · foundations → features → screens → wrap-up
> - Planned dates only when a person sets them: `[planned:: 2026-11-01] [due:: 2026-11-03]` (the AI never guesses them)
> - `[started:: …]` · `[finished:: …]` are stamped by `lantern task start|done`. Don't write them by hand
> - Screen tasks get `[screen:: screen name]`; if something is unknown, end the line with `❓ Needs answer`
> - When a task falls outside the purpose in the work's name, take it out and suggest divide and place with `/l-plan` (one work = one purpose)

## Tasks

- [ ] ${work_id}-T01 {{Task (required)}} [size:: {{S · M · L}}] [ac:: {{AC-1}}]

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-10-29 | Divide works by their purpose, not by the number of tasks |
