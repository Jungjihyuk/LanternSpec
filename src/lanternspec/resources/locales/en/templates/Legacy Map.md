---
id: LEGACY-map
type: legacy-map
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Legacy Map
template_version: 1.0.2
based_on: 1.0.2
---
# 🗂 Legacy Map

> [!abstract] At a glance
> {{The state of the existing documents, in one sentence (required)}}

> [!guide]- ✍️ How to write — keep originals, pick one route each
> Keep the original documents in this folder **as they are**; never edit them. Pick how to handle each document (its 'route').
> - 🧽 Absorb — copy only the essentials into a `3. Current State` document and link the original
> - 🗄 Archive — don't copy anything; just keep a link
> - 🚚 Move — move it whole, fitted to a template (`/l-template migrate`)
>
> `/l-init` recommends a route; the person only confirms.

## Documents
| Document | What it covers | Still true? | Route | New place |
|---|---|---|---|---|
${legacy_rows}

## Idea candidates (TODO · later)
> [!guide]- ⚙️ Generated section — move only what's worth keeping with /l-idea
> Lines gathered by `lantern legacy todos`. Move only the ones worth keeping with `/l-idea`.

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
| 1.0.2 | 2026-11-11 | Notes folded, under titles that say what they are |
