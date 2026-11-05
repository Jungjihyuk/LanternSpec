---
id: CUR-server-ops
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Server Operations
template_version: 1.0.1
based_on: 1.0.1
code: []
checked_commit: ""
---
# 📘 Server Operations

> [!abstract] At a glance
> {{Where and how the server or outside service (Supabase and so on) runs, in one sentence (required)}}

## Environments
| Environment | Where | Address | How it deploys |
|---|---|---|---|
| {{Production}} | {{Where}} | {{Address}} | {{How}} |

## Operations
- Logs · monitoring: {{Logs}}
- Backups: {{Backups}}
- Secrets: {{Secrets}}
- Access permissions: {{Permissions}}
- Pricing · usage limits: {{Limits}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-05 | Fits projects on an outside service too; added access permissions and usage limits |
