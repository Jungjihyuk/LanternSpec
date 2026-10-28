---
id: CUR-platform
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Platform Integration
template_version: 1.0.0
based_on: 1.0.0
code: []
checked_commit: ""
---
# 📘 Platform Integration

> [!abstract] At a glance
> {{Which platform features it works with, in one sentence (required)}}

<!-- lantern:if clients=mobile -->
## Mobile
- Push notifications: {{Push notifications}}
- Deep links: {{Deep links}}
- Permissions (camera · location …): {{Permissions}}

<!-- lantern:endif -->
<!-- lantern:if clients=web -->
## Web
- Web push: {{Web push}}
- Supported browsers: {{Browser support}}
- PWA · offline: {{PWA}}

<!-- lantern:endif -->
<!-- lantern:if clients=desktop -->
## Desktop
- Notifications: {{Notifications}}
- URL scheme: {{URL scheme}}
- Launch at login · tray: {{Launch at login}}

<!-- lantern:endif -->

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
