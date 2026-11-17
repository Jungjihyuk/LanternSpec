---
id: CUR-design-system
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Design System
template_version: 1.0.0
based_on: 1.0.0
---
# 📘 Design System

> [!abstract] At a glance
> {{How the screens should feel, in one sentence (required)}}

> [!guide]- ✍️ How to write — what every screen follows
> Write only **what every screen follows** (colors · type · spacing · corners · shared parts), not one screen.
> What differs per screen is drawn in the work's `Design.md`.
> - Write values as the code uses them (`#1A1C1E` · `16px`). If the code names them, write the name too
> - `/l-design` reads this document before making screen mockups
> - If the repository has a `DESIGN.md`, that file is the reference. Don't repeat its values here; only link it
> - The sections come in the order of the standard `DESIGN.md` (Google Labs). Delete the ones you don't need
> - Material from outside, such as a company brand guide, goes in `📚 Domain Knowledge/` and is linked from here

## Overview
{{Who the screens are for and the impression they should give}}

## Colors
| Name | Value | Where it is used |
|---|---|---|
| {{Name}} | {{Value}} | {{Where it is used}} |

## Typography
| Use | Typeface | Size | Weight |
|---|---|---|---|
| {{Use}} | {{Typeface}} | {{Size}} | {{Weight}} |

## Layout
- {{The base spacing unit and how the layout changes with screen width}}

## Elevation & Depth
- {{Whether shadows are used and how layers are shown}}

## Shapes
- {{Corner rounding and borders}}

## Components
| Part | Look | States |
|---|---|---|
| {{Part}} | {{Look}} | {{States}} |

## Do's and Don'ts
- {{Do}}
- {{Don't}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-17 | Base template |
