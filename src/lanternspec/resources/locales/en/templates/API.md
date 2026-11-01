---
id: CUR-api
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: API
template_version: 1.0.1
based_on: 1.0.1
code: []
checked_commit: ""
---
# 📘 API

> [!abstract] At a glance
> {{The API style and how it authenticates, in one sentence (required)}}

> [!guide] The exact shape of requests and responses: **the code is the reference**.
> - If documentation can be generated from the code (OpenAPI …), link the result
> - Keep only the list of endpoints and the common rules here

## Common rules
- Authentication: {{Authentication}}
- Error format: {{Error format}}

## Endpoints
| Method | Path | What it does | From work |
|---|---|---|---|
| {{GET}} | `{{/path}}` | {{What it does}} | {{Work link}} |

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
