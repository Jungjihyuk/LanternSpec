---
name: l-adr
description: Record a decision (ADR) — record a hard-to-reverse decision (database · framework · auth method · outside service · data structure change · public API change · a change of direction) in <<folder.rules>>/ADR-NNN with context · options considered (pros and cons) · decision · consequences · status. Use when an important, hard-to-reverse decision is made, or /l-design · /l-build · /l-sync hit one.
invocation: model
argument-hint: "<what to decide> [--work W-NNN]"
---

# /l-adr — record a decision

**Purpose:** leave a record that answers "in six months, why did we do this?".

## Record it?
- **Record:** tool choices that are hard to change (database · framework · auth method · outside service) · data structure changes · public API changes · decisions that changed direction (an intent change found by `/l-sync`)
- **Don't record:** small libraries (one line in the work's `<<file.record>>`) · code cleanup
- The AI **only suggests**; the person decides whether to record it. But **data structure changes are always** recorded.

## Steps
1. Create:
   ```bash
   lantern scaffold adr "<what to decide>" [--work W-012]
   ```
2. Fill in: <<marker.glance>> (the decision in one line) · context (what had to be decided, and why now) · options considered (pros and cons of each — keep the ones not chosen) · decision (what, the deciding reason, who · when) · consequences (what gets easier · harder · which documents change).
3. Status: starts as `<<adr_status.proposed>>`. When the person decides, `lantern meta set "<ADR file>" status="<<adr_status.accepted>>"`.
   When it overturns an earlier decision, mark the old ADR: `lantern meta set "<old ADR>" status="<<adr_status.superseded>>" superseded_by=ADR-NNN`.
4. Link: an `[[ADR-NNN …]]` link in `## Decisions · failed attempts` of the work's `<<file.record>>`; if it came from the design, add the ID to `adr` in `<<file.design>>`'s frontmatter.

## Common wrap-up
```bash
lantern close l-adr [--work W-012]
```
