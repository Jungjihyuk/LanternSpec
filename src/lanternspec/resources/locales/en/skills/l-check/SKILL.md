---
name: l-check
description: Check document formats — check docs/ documents for required blanks · enums.yaml values · broken links · leftover {{blanks}} · old template versions · duplicate IDs · document length · task format with lantern check, explain the result and suggest fixes. Use before committing, after a template version changed, or when the user asks whether docs follow the templates.
invocation: model
argument-hint: "[document path | --changed | --epic W-NNN]"
---

# /l-check — check document formats

**Purpose:** the script decides. You **explain the result and suggest fixes**.

## Steps
1. Check:
   ```bash
   lantern check                 # everything
   lantern check --changed       # before committing: changed documents only
   lantern check "<path>"         # one document
   lantern check --epic W-012    # acceptance-criteria rules (one meaning? checkable?)
   ```
2. Explain the result in groups: **✖ errors** (broken links · wrong values · duplicate IDs · missing required sections) → **⚠ warnings** (required blanks · long documents · templates that changed a lot) → **ℹ notes** (blanks · <<marker.unknown>> · templates with new sections).
3. Suggest fixes:
   - Required blanks → ask what to fill in, or `<<marker.unknown>>` if unknown
   - Wrong values → a value from `docs/<<folder.templates>>/_meta/enums.yaml` (suggest adding one to enums.yaml if a new value is needed)
   - Broken links → suggest the right document name · path
   - Template changed a lot (major) → `/l-template migrate "<document>"`
   - Long document → split the section the check pointed at into its own document and link it
   - `<<marker.unknown>>` → list them and ask whether the answers are available
   - "… section is missing. … Did you change it on purpose?" (protected section) → don't fix it; ask which of three: renamed it (`lantern sections rename <key> "new title"`) · not using that feature (`lantern sections off <key>`) · a mistake (restore the section from the template)
4. Fix things if the user wants. Never change the template structure (sections · headings). After fixing, check again with `lantern check`.

If you changed documents, the common wrap-up: `lantern close l-check`.
