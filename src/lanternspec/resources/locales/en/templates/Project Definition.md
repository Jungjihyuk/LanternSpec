---
id: CUR-project
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Project Definition
template_version: 1.0.1
based_on: 1.0.1
code: []
checked_commit: ""
---
# 📘 ${project} — Project Definition

> [!abstract] At a glance
> {{This project in one sentence (required)}}

## What kind of project
> [!guide] ⚙️ A table copied from your answers to `/l-init` (`lantern.yaml`).
> Don't edit it here; to change it, run `/l-init` again.

${profile_table}

## Who it is for
> [!guide] Who mainly uses it, and what problem those people have today.

{{Main users and their problem (required)}}

## Goals
> [!guide] 2–4 results that would let you call this project a success. Write them so you can check whether they were reached (e.g. "sign-up finishes within 3 minutes").

- {{Goal (required)}}

## Not doing
> [!guide] What this project has decided not to do. If it might happen someday, keep it as an idea (`/l-idea`) instead of here.

- {{Not doing}}

## Key terms
> [!guide] Only the few words needed to understand this project.
> The full list of terms and the 'words to avoid' go in [[${path.glossary}]].
> `lantern check` reads only the glossary.

| Term | Meaning |
|---|---|
| {{Term}} | {{Meaning}} |

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
