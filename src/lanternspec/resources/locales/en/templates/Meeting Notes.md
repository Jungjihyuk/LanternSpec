---
id: ${id}
type: meeting
status: ${meeting_status.draft}
created: ${today}
updated: ${today}
links: []
template: Meeting Notes
template_version: 1.0.1
based_on: 1.0.1
attendees: []
---
# 🗣 ${today} ${name}

> [!abstract] At a glance
> {{What was decided, in one line (required)}}

## Agenda
- {{Agenda item}}

## Decisions
- {{Decision}}

## Action items
> [!guide] Don't leave action items here: move them into ideas (`/l-idea`) or a work's tasks, then link where they went.

- {{Action item}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
