---
id: CUR-data
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Data
template_version: 1.0.1
based_on: 1.0.1
code: []
checked_commit: ""
storage: ${variant}
---
# 📘 Data

> [!abstract] At a glance
> {{Where and how data is stored, in one sentence (required)}}

> [!guide] The data structure is edited in one place: `schema.dbml` in this folder.
> - The ERD and data dictionary below are made from `schema.dbml` by `lantern dbml render`. Don't edit them by hand
> - In an existing project the real database (its migration files) is the reference; `schema.dbml` is made from it with `lantern dbml from-sql`

## Where it is stored
- Kind: ${variant}
- {{Store · how it connects}}

## ERD
<!-- lantern:erd:start -->
<!-- lantern:erd:end -->

## Data dictionary
<!-- lantern:dictionary:start -->
<!-- lantern:dictionary:end -->

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
