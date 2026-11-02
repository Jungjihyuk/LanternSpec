---
name: l-ref
description: Bring in references — company rules, a glossary or domain knowledge (laws · policies · specs), inside the project or outside it; check their structure, index them, then propose per section how it is used (for company rules, scope and strength) for approval. Use when the user wants to bring in company rules, a glossary, or domain documents for the AI to follow.
invocation: manual
argument-hint: "[rules|terms|domain] <path>"
---

# /l-ref — bring in references

**Purpose:** leave people's material as it is, in whatever form, and index it so the AI can find and read just the section it needs.
The original is not changed (except adding headings to material inside the project, with approval).

Input: `$ARGUMENTS` — `<kind> <path>`. The kind matches the keys of `references` in `lantern.yaml`.

| Kind | What material | When it reaches the AI |
|---|---|---|
| `rules` | Company rules — must be followed, short | Always (verbatim in AGENTS.md) |
| `terms` | Glossary — what words mean · words not to use | Only a one-line rule always; the table when needed |
| `domain` | Domain knowledge — large, many documents, needed now and then | Only when needed (just that section, found through the index) |

Without a kind, skim the material, recommend one from the table and confirm.

## Material outside is never opened directly
A `~/…` or absolute path is **outside** the project. Don't open such files with the file-reading tool; read them only through `lantern ref check` · `lantern ref read "<document>#<section>"`.
Some AI tools ask permission for every read outside the working folder, and a run nobody watches simply fails.
Never copy an outside document's path, titles or text into files that go into git (documents · code · commit messages).

## 1. Receive
- Check the path. The index reads only `.md`. For inside PDF · Word · PowerPoint · HWP · Excel files, `lantern ref convert` makes copies **in the same folder** (step 0 of `domain.md`). The originals stay as they are.
- Never open an original with file-reading tools to copy it out. Outside originals are converted to `.md` by the person.
- The person decides whether it lives inside the project or outside. Keep material that must not be published outside — neither its path nor its index goes into git (`.lantern/references.yaml`).

## 2. Look at the structure
```bash
lantern ref check <path>
```
- A ⚠ means the document is hard to read section by section (no headings · a skipped heading level · a very long section).
  - **Inside:** keep the content and propose only `##` headings to add → add them once approved.
  - **Outside:** don't change the original. Say what the problem is; the person decides whether to fix the original or leave it.

## 3. Index
```bash
lantern ref index <kind> <path>
```
- A path not listed yet is added: an inside path to `lantern.yaml` `references.<kind>` (shared with the team), an outside path to `.lantern/references.yaml` (yours only).
- In the output, `+` is a new section, `~` a changed one, `-` one that is gone. The next step handles only `+` · `~` — bringing the material in again doesn't ask about sections already approved.

## 4. Choose by kind
Read and follow only that kind's file in this folder: `rules.md` · `terms.md` · `domain.md`.

## 5. Finish
```bash
lantern close l-ref
```
