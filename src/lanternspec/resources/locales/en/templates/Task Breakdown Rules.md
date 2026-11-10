---
id: CUR-task-rules
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Task Breakdown Rules
template_version: 1.0.0
based_on: 1.0.0
---
# 📘 Task Breakdown Rules

> [!abstract] At a glance
> The rules for splitting a design into tasks.
> `/l-task` uses them to size each task and to decide where an unknown goes.
> `/l-build` handles spike tasks by them.
> Change any rule that doesn't fit this project. The AI follows the changed rules.

## Size
Set by how long a person would take, working without interruption. It is not the time the AI actually takes.

| Size | This kind of work | Example |
|---|---|---|
| `${size.xs}` | Change one fixed value, wording or setting. No new tests needed | Fix a message, add an environment variable, add one link |
| `${size.s}` | Change one or two files the way things are already done. Nothing new to decide | Add a field to an API response, one input check function |
| `${size.m}` | Change several files and write new tests, within one layer: data, API or screen | A sign-up API, a database connection with its first migration |
| `${size.l}` | Span several layers (data, API, screen), or bring in a technology or outside service used for the first time | Sign-in with sessions and a lockout policy, a payment integration |

- **Split anything that looks bigger than `${size.l}`.** Work longer than a day is hard to review, and when it gets stuck you find out late.
- **When unsure, pick the larger size.** Finishing early disturbs a plan less than running over.

## Where an unknown goes
| Kind of unknown | Where it goes | Example |
|---|---|---|
| A question unrelated to the current work | An idea card (`/l-idea`) | "Should we move to GraphQL someday?" |
| A choice this work needs that can be settled by weighing it up | Decided in design (`/l-design` → ADR) | Keep sign-ins with sessions or with JWTs |
| Something this work needs that can only be learned by trying | A spike task (see "Spike tasks" below) | Does the payment service really support partial refunds? Does this library handle 10,000 items in a second? |
| Something only a person can answer | `❓ Needs answer` on that line | How many days do refunds stay possible? |

- **Decide before you spike.** Don't turn a choice you can settle by weighing it up into a spike task.
- **Don't fill gaps with guesses.** Mark what only a person can answer; that task doesn't start until the answer comes.

## Spike tasks
A task that finds out something only trying can tell. What it produces is a conclusion, not code.

```
- [ ] W-005-T01 [spike] Check the payment service supports partial refunds [size:: ${size.s}] [ac:: AC-4]
- [ ] W-005-T02 Refund API [size:: ${size.m}] [ac:: AC-4] [after:: T01]
```

- **The size is a time limit.** If there is no conclusion within it, stop and ask a person.
- **Put the tasks that depend on the conclusion after the spike** (`[after:: T01]`), so building doesn't start without it.
- **Record the conclusion like this.**
  - If it settles what to choose, write an ADR with the evidence checked (call results, where the trial code is).
  - If it only establishes a fact, write it in the work's `Log.md`.
- **Don't reuse the trial code as is.** If it's needed, rebuild it properly in a building task.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-11 | Base template |
