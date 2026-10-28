---
id: CUR-data
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Data
template_version: 1.0.0
based_on: 1.0.0
code: []
checked_commit: ""
storage: ${variant}
---
# 📘 Data

> [!abstract] At a glance
> {{Where and how data is stored, in one sentence (required)}}

> [!guide] The source is `schema.dbml` in this folder (where people and the AI edit). The ERD and data dictionary below are **generated** from the DBML by `lantern dbml render`; don't edit them by hand. In an existing codebase the migrations and the real database are the reference, and the DBML is rebuilt from them (`lantern dbml from-sql`).

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
