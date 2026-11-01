---
id: ${work_id}
type: design
status: ${work_status.design}
created: ${today}
updated: ${today}
links: ${links}
template: Design
template_version: 1.0.1
based_on: 1.0.1
parts: []
approved: ""
adr: []
---
# 📐 ${work_id} ${name} — Design

> [!abstract] At a glance
> {{How you decided to build it, in one sentence (required)}}

> [!guide] Write **only what changes** in this work.
> - Of 🏗 Structure · 🎨 Screens · 🗄 Data, delete the sections you don't need
> - List the ones you keep in the `parts` property at the top (e.g. `[structure, data]`)
> - When a person approves it, `lantern design approve` writes the date and name into `approved`

## 🏗 Structure
> [!guide] Draw the parts and flows that change with Mermaid; the text explains the diagram.

```mermaid
flowchart LR
  A["{{Part}}"] --> B["{{Part}}"]
```

{{Structure notes}}

## 🎨 Screens
> [!guide] The **picture** is the reference; the text explains it.
> - Keep mockups as files (images · HTML exports) under the work's `Screens/` folder and link them
> - Don't use share links such as Figma's. They may change or stop opening later

| Screen | Mockup file | Notes |
|---|---|---|
| {{Screen name}} | `Screens/{{File}}` | {{Notes}} |

## 🗄 Data
> [!guide] Write in DBML **only the tables and columns that change** from the current data structure (`3. Current State/Data/schema.dbml`).
> - When the work is done, `/l-build` merges them into `schema.dbml`
> - Check the syntax with `lantern check-dbml`

```dbml
// {{Tables that change}}
```

| Change | Table · column | Why |
|---|---|---|
| {{Add · change · remove}} | {{Target}} | {{Why}} |

**Migration plan:** {{Migration plan}}

## Hard-to-reverse choices
> [!guide] If there is a choice that will be hard to undo later, write it here and record the decision with `/l-adr`. Otherwise "None".
> For example: choosing or changing a database · framework · auth method · outside service, or changing the data structure or a public API

{{Hard-to-reverse choices}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-10-27 | Base template |
| 1.0.1 | 2026-11-02 | Clearer writing guides (long ones split into lines, symbols and internal names in words) |
