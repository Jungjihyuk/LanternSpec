---
id: ${work_id}
type: tasks
status: ${work_status.tasks}
created: ${today}
updated: ${today}
links: ${links}
template: Tasks
template_version: 1.2.0
based_on: 1.2.0
---
# ✅ ${work_id} ${name} — Tasks

> [!abstract] At a glance
> {{How many tasks there are and in what order they go, in one sentence (required)}}

> [!guide] One task per line. For example:
> `- [ ] W-012-T02 What [size:: ${size.m}] [ac:: AC-1] [after:: T01]`<!-- lantern:if team --> `[owner:: name]`<!-- lantern:endif -->
> - `[name:: value]` is a property of the task. `size` is ${size.xs} · ${size.s} · ${size.m} · ${size.l} (see `3. Current State/Rules/Task Breakdown Rules.md`), `ac` is the acceptance criterion this task meets, `after` is a task that must finish first
> - Order them **the way they are best worked on**: what must finish first → data · foundations → features → screens → wrap-up
> - Planned dates only when a person sets them: `[planned:: 2026-11-01] [due:: 2026-11-03]` (the AI never guesses them)
> - `[started:: …]` · `[finished:: …]` are written by `lantern task start` · `lantern task done`. Don't write them by hand
> - `[by:: …]` is who actually did the task: people and AI models (e.g. `claude-opus-5-5` · `Jihyeok, gpt-5.1-codex`). `lantern task done --by` writes it; a person who did a task may write their own name
> - Screen tasks get `[screen:: screen name]`; if something is unknown, end the line with `❓ Needs answer`
> - When a task falls outside the work's purpose, take it out and suggest placing it separately with `/l-plan`

## Tasks

- [ ] ${work_id}-T01 {{Task (required)}} [size:: {{${size.xs} · ${size.s} · ${size.m} · ${size.l}}}] [ac:: {{AC-1}}]

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-10-29 | Divide works by their purpose, not by the number of tasks |
| 1.0.2 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
| 1.1.0 | 2026-11-11 | Sizes are 15m · 1h · 4h · 8h, defined in the Task Breakdown Rules document |
| 1.2.0 | 2026-11-11 | `[by:: …]` for the people and AI models who actually did a task |
