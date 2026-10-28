---
id: CUR-deploy
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Deployment
template_version: 1.0.0
based_on: 1.0.0
code: []
checked_commit: ""
---
# 📘 Deployment

> [!abstract] At a glance
> {{Where and how it is deployed, in one sentence (required)}}

<!-- lantern:if clients=mobile -->
## Mobile
- Store review: {{Store review}}
- Version · build number rules: {{Version rules}}
- Test releases (TestFlight · internal testing): {{Test releases}}

<!-- lantern:endif -->
<!-- lantern:if clients=web -->
## Web
- Hosting: {{Hosting}}
- Domains · environments (staging · production): {{Environments}}
- How it deploys (CI): {{How it deploys}}

<!-- lantern:endif -->
<!-- lantern:if clients=desktop -->
## Desktop
- Signing · notarization: {{Signing · notarization}}
- Distribution (download · store): {{Distribution}}
- Auto-update: {{Auto-update}}

<!-- lantern:endif -->

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
