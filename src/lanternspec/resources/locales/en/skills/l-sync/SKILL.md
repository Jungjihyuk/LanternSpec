---
name: l-sync
description: Bring docs and code back in line — with lantern scan, find unowned commits (no work ID) · stale documents whose code changed after their last check · unrecorded schema changes · DBML vs migration drift · failing acceptance tests; for each, recommend a direction by the reference table (what · why → docs, how → code, data → migrations) and align after the person confirms. Use after code was edited by hand or plans changed mid-work.
invocation: model
argument-hint: "[--tests]"
---

# /l-sync — bring docs and code back in line

**Purpose:** drift always happens. Notice it early (the script) and align it easily (you + the person).

## 1. Find (the script)
```bash
lantern scan [--tests]
```
`--tests` also runs the acceptance tests with `build.test` from `lantern.yaml`.

## 2. Align — recommend a direction for each item; the person confirms
| Content | Reference (source) | When they differ |
|---|---|---|
| What · why (plan · acceptance criteria) | **Docs** | Fix the code → add a task `lantern task add W-012 "<align>" --size S --ac AC-n`. If the intent changed, fix the docs first and `/l-adr` |
| How (structure · functions · screen details) | **Code** | Update the docs to match the code |
| Data (schema) | **Migrations** | Re-align the DBML: `lantern dbml diff --sql <migrations folder>` → fix `schema.dbml` → `lantern dbml render` |

- **Unowned changes:** ask which work they belong to →
  ```bash
  lantern sync adopt <commit> --work W-012          # link it in that work's <<file.record>>
  lantern sync adopt <commit> --none "<why>"        # record it as a change without a work
  ```
- **Stale documents:** after matching the content to the code, move the check point forward: `lantern meta set "<document>" checked_commit=$(git rev-parse --short HEAD)`
- **Unrecorded schema changes:** one line in `## <<section.schema>>` of that work's `<<file.record>>` (date · change · why · migration file). Data structure changes get an `/l-adr` too.
- **Failing acceptance tests:** if the plan is right, a task to fix the code; if the plan is outdated, fix the plan + `/l-adr`.
- **Commits mixing several tasks:** only mention it (one task = one commit from now on).

When changing the plan or design, never quietly overwrite the source: write **what changed** in the decisions section of the work's `<<file.record>>` first, then merge.

## 3. Common wrap-up
```bash
lantern scan            # check again — report only what is left
lantern close l-sync
```
Report: what was aligned · what is left · what the person has to decide.
