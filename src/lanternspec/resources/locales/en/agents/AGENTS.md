## LanternSpec — how the AI works in this project

> The person leads, the AI is a team member, and documents are the work reports. Idea → plan → design → tasks → build
> flow through familiar development documents, and when an unfamiliar technology comes up, it is compared with your
> knowledge store to show what to review and what to learn.

### Document map (`docs/`)
| Folder | What | Who edits it |
|---|---|---|
| `<<file.moc>>` | The map. Read in this order: MOC → <<folder.current>> → (only the works you need) <<folder.works>> | `lantern map` (inside the marks) |
| `<<folder.templates>>/` | Document structure (templates) · `_meta/enums.yaml` = the one source of the fixed choices | `/l-template` |
| `<<folder.ideas>>/` | `IDEA-001 …md` | `/l-idea` |
| `<<folder.works>>/W-012 …/` | Plan · design · tasks · log. **The only place you edit while working** | `/l-plan` → `/l-design` → `/l-task` → `/l-build` |
| `<<folder.current>>/` | How the system looks now. Updated **only when a work finishes**, after approval | `/l-build` wrap-up · `/l-sync` |
| `<<folder.ops>>/` | Reports (`<<file.report>>`) · meeting notes | `/l-report` |
<!-- lantern:if knowledge -->
| `<<folder.debt>>/` | Understanding-debt cards (one card = one debt) | `/l-learn` |
<!-- lantern:endif -->
<!-- lantern:if project.origin=brownfield -->
| `<<folder.legacy>>/` | Original legacy documents. **Never edit them** | — |
<!-- lantern:endif -->

### Rules
1. **Scripts own the format, the AI owns the content.** Numbering · files · folders · checks · status changes go through `lantern …` commands. Never make up IDs or create files by hand.
2. **Documents are born from templates only.** Create them with `lantern scaffold …` and fill only the `{{blanks}}`. Don't change the sections or headings. Once written, the `> [!guide]` notes may be deleted.
3. **Don't guess what you don't know.** Write `<<marker.unknown>>` and ask the person.
4. **The common wrap-up.** A skill that changed documents ends with `lantern close <skill> [--work W-012]` (check → map → run record).
5. **Show before writing.** `<<folder.current>>` · design approval · big changes: show a summary and get approval first (exception: `/l-idea` records right away).
6. **Other people's stores are read-only.** Read the knowledge store only through `lantern knowledge`; write only after approval.
7. **Never edit legacy documents.** When you meet a related document in `<<folder.legacy>>/`, ask whether to move it into our templates (`/l-template migrate "<<folder.legacy>>/…"`).
8. **Each fact in one place.** Don't copy content from another document; bring it in with a `[[link]]`. Don't edit generated parts (ERD · reports · MOC block) by hand.
9. **Talk to the user in English.** Questions, explanations, wrap-up reports and document content alike (`project.language` in `lantern.yaml`: `<<project.language>>`). Leave commands, file names and code as they are.
10. **How to ask.** For a question with choices, offer only real candidates — the question tool already adds a free-text option at the bottom, so don't add empty options like "Type your own" or "Pick Other". For a free answer with no candidates (an introduction, a name …), ask in a plain message without options.
11. **People decide about protected sections.** Never delete or rename on your own the sections lantern reads and writes (listed in `<<folder.templates>>/_meta/<<file.sections_page>>`). When a check or wrap-up says "… section is missing. … Did you change it on purpose?", **don't put the section back**; ask the user which of three it is — renamed it → `lantern sections rename <key> "new title"` · not using that feature → `lantern sections off <key>` · a mistake → restore the section from the template.

<!-- lantern:principles -->

### Commits
- One task = one commit. End the message with the ID: `feat: add login button [W-012-T02]` (never mix several tasks)
<!-- lantern:if docs.remote=shared -->
- Documents (`<<file.tasks>>` check-offs · `<<file.record>>` evidence) go in **the same commit** as the code
<!-- lantern:endif -->
<!-- lantern:if docs.remote=local -->
- Commit documents **separately** in `docs/` (the docs-local branch) and point to the code commit: `git -C docs commit -m "docs: W-012-T02 log (code a1b2c3d)"`. Never put `docs/` in a code commit
<!-- lantern:endif -->

### Commands at a glance
| To do this | Command |
|---|---|
| Set up the project · change what kind it is | `/l-init` |
| Capture a thought | `/l-idea` |
| What · why → how → tasks → build | `/l-plan` → `/l-design` → `/l-task` → `/l-build` |
| An unfamiliar technology | `/l-learn` |
| Where things stand | `/l-report` |
| Make · refine · migrate templates | `/l-template` |
| Check formats · align docs and code · map · decisions | `/l-check` · `/l-sync` · `/l-map` · `/l-adr` |
| Work mode (harness · loop · graph) · AI work evaluation | `lantern harness suggest` · `lantern eval` |

In Codex, call them with `$`, like `$l-init`. To see where things stand, `lantern status`; for every command, `lantern --help`.
