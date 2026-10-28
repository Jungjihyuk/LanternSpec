---
name: l-template
description: Make · refine · migrate templates — turn a readable sample (document · capture · description) into a blank template ({{blanks}} · > [!guide]) (new), check an existing template's readability and show improvements before/after (refine), and move existing documents to a changed template's structure (migrate — no content is lost). Use when a new document type is needed, a template should be improved, or docs must move to a new template version.
invocation: model
argument-hint: "new | refine <template> | migrate [<template> | <document path>]"
---

# /l-template — make · refine · migrate templates

**Purpose:** turn a **structure that reads well** into a template, keep refining it, and move existing documents to new templates. Templates live in `docs/<<folder.templates>>/`, where the user shapes them to suit themselves.

Input: `$ARGUMENTS` — `new` · `refine <<doc.plan>>` · `migrate` · `migrate <<doc.plan>>` · `migrate "<<folder.works>>/W-012 …/<<file.plan>>"` · `migrate "<<folder.legacy>>/old <<file.plan>>"`

## Template rules
- A blank to fill is `{{blank name}}`, a required one `{{blank name <<marker.required>>}}` — never use `|` (it breaks tables)
- No blank named `date` · `time` · `title` (Obsidian's core templates replace them)
- Writing guides are `> [!guide] …` (may be deleted once written). Mark each section in its guide as **🟦 Source section / 🔗 Linking section**
- Values the script fills are `${id}` · `${today}` · `${name}` · `${work_id}` · `${links}` … (never touch them)
- The "<<marker.glance>>" box at the top is required: `> [!abstract] <<marker.glance>>` + `> {{… <<marker.required>>}}`
- Common frontmatter: `id · type · status · created · updated · links · template · template_version` (+ `based_on`, templates only)
- At the very bottom, a `## <<marker.changelog>>` table after `<!-- lantern:template-only -->` (not copied into documents)

## Make `new`
1. Pull the structure out of the sample: title · sections · tables · places for diagrams · <<marker.glance>>. With a file, start from a skeleton:
   ```bash
   lantern template new "<template name>" --from "<sample file>"     # preview only (nothing saved yet)
   ```
2. Remove the content and replace it with `{{blanks}}` and `> [!guide]` notes. Mark each section as source / linking.
3. Add the common frontmatter; `type` is one of `doc_type` in `enums.yaml` (suggest adding a new type if needed).
4. **Preview → approval → save:** `lantern template new "<name>" --from "<sample>" --apply`, or save the refined content as `docs/<<folder.templates>>/<name>.md` → `lantern template lint "<name>"`
5. To create a document from the new template: `lantern scaffold custom "<template>" "<path.md inside docs>"`

## Refine `refine <template>`
1. Check readability:
   ```bash
   lantern template lint "<template>"
   lantern template usage "<template>"     # blanks that are always empty in real documents
   ```
   Also look at: is there a <<marker.glance>>? · is text used where a table or diagram would read better? · are blank names clear at a glance? · is it too long?
2. Show the improvements **before and after**, side by side. Never rename or remove protected sections (`docs/<<folder.templates>>/_meta/<<file.sections_page>>`) — if one really must change, say what that section does and let the user decide.
3. Approval → save → bump the version. The script decides the version from what changed; the person only confirms:
   ```bash
   lantern template level "<template>"                       # patch (guides only) · minor (blanks added) · major (blanks removed · renamed)
   lantern template bump "<template>" --auto --note "<what changed>"
   ```
4. For a major change, suggest migrating (see the targets with `lantern template outdated "<template>"`).

## Migrate `migrate` — rules that keep every piece of content
1. See the targets: `lantern template outdated` (only documents still in use — `<<folder.current>>` · works in progress. Don't suggest finished works or `<<folder.legacy>>`; do those one by one if wanted)
2. Build a map from old sections → new sections (renamed · merged · split). Preview:
   ```bash
   lantern template migrate "<template | document>" [--map "old section=new section" …]
   ```
3. Content that maps moves to its new place; **content that doesn't map is never deleted** — it is gathered in `## <<marker.migrate_bin>>` at the bottom of the document → the person tidies it up.
4. Show what changes in each document and get approval → `--apply`. git is the safety net.
5. **Legacy documents (<<folder.legacy>>) into our templates:** `lantern template migrate "<<folder.legacy>>/<document>.md" --to <template> --dest "<new path.md inside docs>" [--apply]` — leaves the original as it is and creates a new document. Fill the new-place column of the legacy map.

## Common wrap-up
```bash
lantern close l-template
```
