# Changelog

**English** · [한국어](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.ko.md)

All notable changes to this project are recorded here, version by version.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (refreshes skills, templates, Obsidian settings and the bundled plugins). `lantern upgrade --apply` renames 0.3.1's sizes (`half` · `1d`) to `4h` · `8h`

### Added
- **Lantern Kanban (Obsidian)** — works as cards in stage columns (plan · design · tasks · build · done); clicking a card opens that work's tasks in a window. It shows works waiting for a person, blocked tasks, and what finished in the last 2 weeks with the time worked. Read only
- **Timeline: a "no date yet" column** — a task with neither actual times nor planned dates waits, with its size, in a column on the right instead of on the time axis; drag it onto a day to plan it. Drag a planned bar back to that column to take its dates off
- **Planned times** — write `[planned:: 2026-11-12 14:00]` with a time and it is drawn at that time. On a 10-minute or hour chart a dropped chip starts at the column it lands on and lasts as long as its size, and moves by columns
- **Who did it `[by:: …]`** — the people and the exact AI model names (`claude-opus-5-5` …) that actually did a task. `lantern task done --by` writes it and `/l-build` leaves its own model name. The timeline and kanban color tasks by people · people with AI · AI

### Changed
- **Task size names** — `15m · 1h · half · 1d` → `15m · 1h · 4h · 8h`. The name is the time: the hours a person would put into the task, added up. Split anything bigger than `8h`
- **Only real times on the timeline** — it draws when work was actually done and dates a person planned. Undated tasks are no longer drawn with a length guessed from their size, so they no longer switch the chart to whole days
- **Note width** — with readable line length on, notes widen to 960px (Obsidian's default is 700px)
- **Plugins turned off stay off** — a bundled plugin is turned on only when it first arrives, and `lantern upgrade` no longer turns one back on. When it is off, reports draw without it
- **The report follows every skill** — `lantern close` remakes the status report, so the kanban and timeline keep up with each skill. Only `/l-report` writes new summary lines
- **Timeline bars and text** — bars are a tint with a solid left edge, and the text always starts where the bar does. A planned bar says how long it is planned for, and changes as it is dragged
- **Order lines** — the arrow is named "Order (before → after)" and its warning "Out of order". Plans by date are compared by date, so the same day is in order
- **Following edits** — change or delete planned dates in `Tasks.md` and the timeline follows without a new report

## [0.3.1] - 2026-11-11

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (refreshes skills, the tasks template and Obsidian settings). `lantern scaffold init` makes the new rules document, and `lantern upgrade --apply` writes older sizes (S · M · L) with the new names

### Added
- **Task Breakdown Rules document** — `Rules/` gets the size table with "split anything bigger than 1d", where an unknown goes (idea · design decision · spike task · needs answer) and how spike tasks work. `/l-task` · `/l-build` read and follow it
- **Spike tasks** — `lantern task add --spike` puts `[spike]` before the title. Its size is a time limit, and its conclusion goes in an ADR or the log
- **The task list as a table (Obsidian)** — task names on the left, size · after · criteria in columns on the right. The file keeps one line per task
- **Timeline: idle time folded** — stretches with no task for an hour or more fold into `⋯ 5 h ⋯`. Column size (5 minutes to an hour) fits the note's width, and a date list moves between days
- **Timeline: time taken** — `T01 · 7 min` beside a finished task, and the total time worked beside a finished work

### Changed
- **Task size names** — `S · M · L` → `15m · 1h · half · 1d` (`반나절` in Korean). The time a person would take with focus; older names are still read
- **Timeline lines** — only "must finish first" is drawn, and in a finished work it appears when a task is pointed at. A bar's tooltip lists what must finish first
- **Timeline legend and marks** — the legend shows only what the chart has, after "one column = 10 min"; the hour row has units; a work's span is a bracket (├──┤); short task names sit beside their bars
- **Empty report views** — a kanban, debt status or timeline with nothing to show is left out, heading and all, and the "views:" line lists only what is shown
- **`lantern enums rename`** — renaming a size renames it on task lines too

### Fixed
- **Tasks piling up on the timeline** — tasks an AI finished in minutes piled into one column with tangled lines
- **Document links in kanban cards** — a task's card carried links like `— [[Design#…]]`

## [0.3.0] - 2026-11-10

**How to move:** `lantern harness suggest` is now `lantern build-mode suggest` (the old name still works for now, with a notice). Where you called `lantern work start` directly while another work was running, go through `/l-parallel` or add `--skip-check`. Codex reads the new permission profile only after the project is trusted, and a `sandbox_mode` in your own settings wins over it (`lantern doctor` points this out).

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (installs `/l-parallel` · `/l-finish` and adds two rules documents, the skills, the project rules and the Codex permission profile)

### Added
- **`/l-parallel` — check before parallel works** — finds what the works must decide together (shared tables · sessions · tokens · permissions · caches) and their order, has a person decide, records it as ADRs, then starts the works. When only one work can start now, it goes in order without a worktree
- **`/l-finish` — wrap up parallel works** — in the base folder, gathers person checks, looks for the same job built two ways, then merges the works one at a time. The current-state update, archive and report happen once, and merged branches are deleted
- **`lantern work overlap`** — shows the tables, files and decision records works share, code files they changed in common, and dependencies they added, without starting anything
- **Tech Selection Criteria document** — `Rules/` gets evaluation criteria, a decision tree and technology comparison tables. `/l-init` recommends a new service's or app's stack by the tree, and `/l-adr` notes the criteria, date and template version
- **Repository File Rules document** — comment structure for `.gitignore` · `docker-compose.yml`, README · CHANGELOG formats by project lifespan, a license chosen by questions, and folder structure. The project AGENTS.md follows it when these files are first created
- **New `/l-init` questions** — how long the project will run (`project.lifespan`), whether the repository is public (public ones get a LICENSE), and, when building a server, whether to set up the development environment with Docker
- **Screen check** — `/l-build` opens and captures each screen task with the AI tool's browser and checks its acceptance criteria. When it can't, it leaves a "waiting for a person" line and carries on, and these are gathered for a person before merging. Setting: `verify.browser`
- **Document auto-commit** — `/l-plan` · `/l-design` · `/l-task` · `/l-adr` commit only their work's documents when they finish (the work folder, the decision records the design follows, linked idea cards). Setting: `docs.commit: auto | manual`; command: `lantern close --commit`
- **Wireframes in `/l-design`** — draws wireframes on the Claude Design canvas and saves them in `Screens/`, keeping the screen before a change in `Screens/Current/`. With an existing UI, `/l-init` mentions `/design-sync` once
- **`lantern template show`** — reads a bundled template the project doesn't have yet
- **One work on another branch** — `lantern work branch · start --into <branch>` starts that work from another branch and merges it there; `--here` commits straight to the current branch with no work branch
- **Codex permission profile** — `lantern install` · `upgrade` add a `lantern` profile to `.codex/config.toml` so Codex can commit, keeping git hooks and config read-only. `lantern work start` shows the command to open the worktree in each tool

### Changed
- **`lantern harness` → `lantern build-mode`** — suggests loop scope, task delegation and parallel works separately. `--apply` changes only the loop scope
- **`/l-plan` lists the screens needed** — it no longer asks for mockups. The "matches the mockup" acceptance criterion is added at design time, and the missing-mockup warning comes only after the design is approved
- **`/l-design` follows earlier decisions** — reads related decision records instead of asking again, and lists the decisions it follows in the design's `adr`
- **Parallel works start after a check** — when two or more works would run at once, `lantern work start` won't start without `--skip-check`
- **`/l-build` in a worktree** — commits only its own tasks and log and stops; `/l-finish` in the base folder wraps up
- **Postponed archiving** — while a work running in another worktree links to it, `lantern work archive` only marks the work done and keeps its folder; `--now` archives it anyway
- **`lantern work list` marks** — shows works waiting for `/l-finish`, branches already merged (with the delete command), worktrees left after a work finished, and works waiting to be archived
- **`/l-init` question order** — asks what you're building before where it's used, in plain choices, and asks to choose only when there are two or more candidates

### Fixed
- **Records mixed between worktrees** — the record saved before a conversation is summarized goes only to that worktree's work, and each worktree keeps its own daily session document
- **The local-mode `docs` link showing as a new file** — it's added to the repository's exclude file so git ignores it
- **Merge conflicts in generated documents** — the base side is taken, and `/l-build` has an order for resolving document, data and code conflicts
- **Finishing a work** — merges in the folder where the base branch is open, leaves a worktree it can't delete whole, and says a failed merge is not a conflict when nothing conflicts

## [0.2.10] - 2026-11-04

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (installs `/l-pr` and puts the new rules in the skills). To use `dev` or PRs, set it like `lantern profile set git.pr=deploy`, then run `lantern upgrade` once more

### Added
- **`/l-pr` — open a pull request** — finds the direction that fits the branch flow, writes the title and body from the commits and work documents, and pushes and opens the PR once confirmed. Only a person can call it, and it never merges
- **Branch flow question in `/l-init`** — choose how work gets merged, out of four: keep it simple · separate development from deployment · a PR for each work · keep what you use now. `lantern work flow` works out the recommendation from the branches and remote
- **Branch settings** — `lantern.yaml` now has `git.branch` (naming rule) · `git.pr` (PR flow) · `git.deploy` (deploy branch). The defaults behave as before
- **Branch naming rule** — set a rule like `feature/{id}-{slug}` and it is followed, and names that break it are refused. A name without the work ID is tied to its work by `branch` in the plan document. `lantern scaffold work --branch` · `lantern work branch --name`
- **Handling what comes up outside the plan** — `/l-build` sorts what isn't in the design: a big change goes to design, a small difference goes in the documents, something outside the purpose becomes an idea card instead of being fixed, and something that must come first stops the work and asks which branch to start from
- **Task order changed by a person** — `lantern task next` warns when the order differs from the last commit, and `/l-build` asks why and goes on once agreed
- **PR title and commit check** — `lantern check-pr` looks for work IDs in the PR title and code commits. It is part of the GitHub check from `lantern install --ci`, warns by default, and fails under `git.hooks: block`
- **PR and commit templates** — `lantern install --pr-template` · `--commit-template` write the template files, and leave existing ones alone

### Changed
- **Install and upgrade output** — the long single line of settings is now one line per file, and "Merged settings" says what actually happens
- **New work branches start from the base branch** — `lantern work branch` branches from `git.base` instead of the current position, so another work's unfinished code doesn't come along. It stops when on another branch; use `--from <branch>` to build on it
- **Finishing a work** — `lantern work finish` brings the base branch into the work branch first, tests that result, then merges. This may add a merge commit on the work branch. It warns when the remote base branch is ahead
- **No AI marks** — commit messages from `/l-build` · `/l-pr` and PRs carry no mark that AI did the work
- **Reading an idea card's source** — `/l-plan` reads only the items a card names from the source document it links

### Fixed
- **A task of another work as a prerequisite** — `lantern task add --after` cut off the work number and pointed at this work's task; it now refuses with an error

## [0.2.9] - 2026-11-03

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (adds the Lantern Timeline plugin to vaults that use Obsidian plugins and turns off a Metadata Menu notice; close Obsidian first, and both apply when it reopens) → `lantern report` to make the report again

### Added
- **A readable timeline plugin** — in projects that use Obsidian plugins, the report's timeline is drawn by the Lantern Timeline plugin: works and tasks on the left, bars by day on the right. Works fold, and clicking a task's name opens its `Tasks.md`. Color and dashes show each state, today and weekends are marked, and a legend explains the marks. Projects without the plugin keep the Mermaid chart
- **Plan by dragging on the timeline** — drag a task that has not started to move it, or drag its ends to change its length. The dates are saved in its planned and due attributes on the task line; its actual start and finish times never change
- **What-comes-after arrows on the timeline** — after relations are drawn as arrows, and turn red when a task that has not started begins before the task it waits on
- **The timeline follows the tasks file** — changes to a checkbox, the start time or planned dates in `Tasks.md` show without `lantern report`. Actual dates, titles and added or removed tasks show when `lantern report` runs again

### Changed
- **Timeline title** — the report's `📅 Timeline (WBS)` is now `📅 Timeline`

### Fixed
- **Document links in the timeline** — `[[…]]` links on a task line are left out of its name, and works are in number order
- **Metadata Menu's notice** — the notice asking for DataviewJS, which LanternSpec doesn't need, no longer appears every time Obsidian opens. DataviewJS stays off

## [0.2.8] - 2026-11-03

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (refreshes the `/l-ref`, `/l-domain`, `/l-idea` and `/l-plan` skills and the Idea and Competency Card templates, adds the "Blocked" idea status to `enums.yaml`, and regenerates the CI workflow in projects that use it)

### Added
- **Converting originals with `lantern ref convert`** — PDF · DOCX · PPTX · HWP · HWPX files in the domain-knowledge folder get a Markdown copy cut into sections, and XLSX · CSV files get a card with sheets, columns, row counts and first rows, next to the original. By default it only lists them; `--apply` writes. It marks the quality (good · check it · no text), converts identical files once, converts again when an original changes but never overwrites a copy edited by hand, and carries on when one file fails. PDF needs `pdftotext` (poppler)
- **Section preview with `lantern ref preview`** — shows a document as each section's address, line count and first lines. `/l-ref domain` proposes descriptions from it instead of the whole text, which saves tokens
- **Blocked ideas** — what is wanted but not possible now, because of a technical limit, skill or experience, stays as the idea status 🚧 Blocked. `lantern idea status IDEA-014 Blocked --reason "…" --revisit "…"` records why and what would reopen it, and the Docs MOC gathers blocked ideas in their own list. When skill is what blocks it, `lantern debt promote IDEA-014` makes a competency card, linked both ways
- **Lint errors in CI with `build.ci_lint`** — `warn` shows the errors and lets CI pass; `block` fails it. When unset, existing projects are `warn` and new ones `block`. Failing tests fail CI either way. Existing projects whose CI used to fail on lint errors now pass, so set `build.ci_lint: block` to keep failing

### Changed
- **Colored status marks** — on a terminal, ✔ in `lantern doctor`, `lantern check` and other commands is green and ℹ cyan, while ⚠ warnings and ✖ problems color the whole line yellow and red. Output sent to a file or pipe, or with `NO_COLOR` set, stays plain as before. The summary at the bottom of `lantern doctor` is in words too, such as "0 problems · 3 warnings"
- **Checks per part** — `lantern lint` and `lantern scan --tests` run each part's (`code.parts`) commands in its folder. A part's command takes over from `build.*`, so everyday `lantern lint` checks every part too. Leave a heavy part out of CI with `ci: false` on that part

### Fixed
- **CI failing in monorepos** — when the package file lives in a subfolder such as `backend/pyproject.toml`, CI ran `uv sync` at the root and failed. Each part (`code.parts`) now prepares its tools in its own folder, with the runner found from that folder's lock file, and the setup command is skipped while the package file is missing
- **"No frontmatter" warning on domain knowledge** — `lantern check` no longer treats domain-knowledge documents, which have no template, as templated documents
- **Unconverted originals went unnoticed** — `lantern doctor` and `lantern ref domain` now say how many originals wait to be converted

## [0.2.7] - 2026-11-02

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (refreshes the default templates, the `/l-template` skill and the Obsidian CSS snippet)

### Changed
- **Clearer template version notice** — `lantern check`'s "template changed" notice now says it is the template's own version, not LanternSpec's ("changed since this document was made … template version 1.0.0 → 1.1.0, not the LanternSpec version"), and shows the command that brings the document along (`lantern template migrate`)
- **Easier-to-read template guides** — the guide boxes of all 22 default templates were reworded. Long guides keep the key sentence on the first line and list the rest; symbols such as ✕ ○ ✚ and setting keys or internal names are said in words; the unexplained "🟦 Source section" mark is gone (only ⚙️ for sections lantern fills and 🔗 for link-only sections remain). The "At a glance" blanks of Plan · Design · Tasks · Log now say what to write. Templates whose wording alone changed get a patch bump, so `lantern check` doesn't flag existing documents
- **Collaboration Rules' "Work units" section is now "Work division"** — matching the `Work Division Rules` document (template 1.1.0)
- **Multi-line guides in sections lantern reads** — in sections lantern reads and writes, such as "Now" and "Domain Knowledge Used", the `>` lines continuing a `> [!guide]` are treated as the guide, not as content

### Fixed
- **The domain-knowledge folder gets a color too** — in Obsidian's file list, `📚 Domain Knowledge` was the only folder without a colored box. With eight folders the colors shift by one in list order: red · orange · yellow · green · teal · blue · violet · pink (`📒 Debt` stays red, `5. Legacy Docs` becomes pink)

## [0.2.6] - 2026-11-01

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (installs the new `/l-ref` and `/l-domain` skills, plan template 1.1.0, and refreshes AGENTS.md rules) → `lantern scaffold init` if you want the glossary and the domain-knowledge folder

### Added
- **Bringing in references (`/l-ref` · `lantern ref`)** — company rules, glossaries and domain knowledge stay where they are, inside the project (relative path) or outside it (`~/…` or an absolute path), and are indexed section by section. `lantern ref index <rules|terms|domain> <path>` shows the new, changed and removed sections, and `lantern ref read "<document>#<section>"` reads just that section (a long one lists the parts to read instead). `lantern ref check` points out structure that is hard to read in parts, such as no headings or skipped heading levels. For outside material, paths, titles and the index all stay in `.lantern/` and never reach git
- **Company rules into AGENTS.md (`lantern ref tag` · `rules` · `exclude`)** — once each section's scope (all · a part folder · a language) and strength (must · should) are approved, inside rules go word for word into the matching root or part `AGENTS.md` (over the length budget, "should" rules keep only their title and the command that reads them). Outside rules leave one content-free line in `AGENTS.md` and are shown by `lantern ref rules <part>`, and the hooks hand the "must" rules over again at the start of a conversation and right after compaction. Sections that don't fit this project are left out with `lantern ref exclude`
- **Glossary and words to avoid (`lantern ref terms` · `glossary` · `term`)** — the project glossary (`3. Current State/Glossary.md`) and the approved company terms show as one table; when a term is in both, the company's wins. Give a term "words to avoid" and `lantern check` finds them in the documents, e.g. "'posting' — write 'job listing'". When a conversation asks what a term means, the hook hands over the glossary's meaning
- **Collecting term candidates (`references.terms_detect`)** — questions about what a word used in the documents means are collected as candidates, and the skill wrap-up (`lantern close`) and `lantern ref terms` ask whether to add them to the glossary (`lantern ref candidate` adds one, `--drop` removes it). The default is `auto`; `ask` and `manual` are also available
- **Domain knowledge (`📚 Domain Knowledge/` · `lantern ref domain` · `describe`)** — laws, policies and business-rule documents put in this folder are indexed without registering them. Note for each section what it covers, when to read it, its key terms and whether its exact words must be followed, and `lantern ref domain` shows the index the AI picks from while `Domain Knowledge MOC.md` shows the same index in Obsidian. Verbatim sections are marked 📌 when read, and right after compaction the hook lists the domain knowledge read today
- **Connecting domain knowledge to a work (`lantern ref attach`)** — `/l-plan` picks the sections a work needs and links them in the plan's new "Domain Knowledge Used" section, `/l-task` assigns each section to the tasks that use it, and `/l-design` reads only the attached sections and asks once whether anything is missing. `/l-build` reads only the sections attached to a task when it starts that task (`lantern ref domain --work W-012 --task T03`). Outside material is never written into the plan, only into `.lantern/`
- **`/l-domain` skill** — when a question or design choice outside the work track depends on domain rules, the AI finds the matching section in the index on its own and reads just that section word for word

### Changed
- **Plan template 1.1.0** — adds the "Domain Knowledge Used" section. Plans made from an older template are not asked about it by `lantern check`, and get the section at the end on their first attach
- **A CLAUDE.md that only imports AGENTS.md is deleted** — `lantern install` and `lantern upgrade` delete a `CLAUDE.md` or `.claude/CLAUDE.md` holding nothing but `@AGENTS.md`, since while one exists Claude Code doesn't read the part `AGENTS.md` files. One with your own text, or any when a `CLAUDE.local.md` exists, is kept

## [0.2.5] - 2026-10-31

### Fixed
- **Folders inside a part are no longer asked about** — when a folder that groups several apps (e.g. `frontend` with `pnpm-workspace.yaml`) is made a part, the app inside it (`frontend/apps/web`) is no longer asked about as an undecided candidate; `lantern parts` shows it as "inside part frontend", and the part's evidence is its own `package.json` instead of "no package file found any more"
- **Deleted folder `AGENTS.md` files are no longer warned about** — a folder `AGENTS.md` deleted but not yet committed kept showing in `lantern doctor` and `lantern upgrade`, both in the "not handed to" warning and in the length budget check

## [0.2.4] - 2026-10-30

Upgrade: `uv tool upgrade lanternspec` → `lantern upgrade` in each project (refreshes the wording of the `/l-init` skill)

### Changed
- **`lantern parts` explained in plain words** — a part is now described as "a sub-project inside the repository (a folder with its own language and check commands)", and running the command first says what a part is and what deciding one does. "Own toolchain" and "manifest" become "package file (pyproject.toml · package.json …)", and with no candidates it says there is no need to split — the root AGENTS.md covers the whole project (`--help`, `lantern doctor`, the `lantern.yaml` comment and `/l-init` use the same words)

## [0.2.3] - 2026-10-30

Upgrade: `uv tool upgrade lanternspec`, then `lantern upgrade` in each project (refreshes skills, agent hooks and AGENTS.md rules)

### Added
- **Rules per folder (`lantern parts`)** — finds folders below the root that have their own manifest (such as `backend` or `frontend/apps/web`) as candidates, and lets you decide with `lantern parts add <folder>` and `lantern parts ignore <folder>` (`/l-init` asks when there are two or more candidates, and `lantern doctor` reminds about undecided ones). With two or more parts, each folder gets an `AGENTS.md` block with its language conventions and check commands, and the root `AGENTS.md` keeps a map of the parts instead of the conventions (with one or none, nothing changes)
- **Handing part rules to tools that don't read folder `AGENTS.md` files** — Claude Code reads folder `AGENTS.md` files itself; for Codex (a `PreToolUse` hook right before the first edit in that part) and Antigravity (the next call after the first edit, plus a short where-we-are reminder on every call since it has no compaction hook), the hooks hand over that part's `AGENTS.md` once per conversation. When there are other folder `AGENTS.md` files not right in a part's folder, `lantern doctor` and `lantern upgrade` name the tools that won't receive them
- **`AGENTS.md` length budget check** — compares the root and every folder's `AGENTS.md` against a budget with margin under what the installed AI tools read in full (Claude Code's 200-line guideline · Codex's 32 KiB · Antigravity's 24,000 bytes per file, and raises the context a Codex hook may add to 8,000 tokens); `lantern doctor` shows each file against the budget and, when over, how much is LanternSpec's block and how much is your own text (`lantern upgrade` warns the same way without stopping)

## [0.2.2] - 2026-10-30

Upgrade: `uv tool upgrade lanternspec`, then `lantern upgrade` in each project (installs the new `/l-resume` skill and adds the conversation records folder to `.lantern/.gitignore`)

### Added
- **Carry on an earlier conversation (`/l-resume` · `lantern resume`)** — whichever tool it was in (Claude Code · Codex · Antigravity), whether it was cut off or finished, shows where it stopped (the last requests · the AI's last words or what it was doing · changed files · uncommitted changes · work in progress) and continues from there. The hooks note each conversation's transcript, so nobody has to find it. Cut-off conversations are marked "⚠ cut off"; only the tail is shown by default, and `--more` reads further back. Conversations are recorded from the moment you upgrade to this version

### Fixed
- `.lantern/.gitignore` was written only when first created, so a personal records folder added by a newer version could show up in git — missing entries are now added

## [0.2.1] - 2026-10-30

### Changed
- **After documents move** — when the rest of the upgrade refreshes documents (templates · MOC · settings) after `lantern upgrade --apply` commits the move, it says how many and asks to review and commit them
- **Small template changes** — `lantern check` and `lantern template outdated` no longer claim new sections; they point to the template's "Changelog" section for what changed
- **Antigravity 1.4.10** — its hook format is unchanged, so `lantern doctor` treats 1.4.10 as a checked version

## [0.2.0] - 2026-10-30

**How to move:** the current-state folders changed (`Rules and Decisions/` → `Rules/` · `Decisions/`, `Deployment` · `Server Operations` → `Deployment and Operations/`, `Work Unit Log` → `Work Division Rules`). After `uv tool upgrade lanternspec`, run `lantern upgrade` in each project to see what would move, then `lantern upgrade --apply`. Commit any uncommitted changes in the documents first (in local mode, if the documents were never committed, commit inside `docs/` first).

Upgrade: `uv tool upgrade lanternspec`, then `lantern upgrade` in each project (refreshes skills, rules, templates and the Obsidian snippet)

### Added
- **Moving documents to the current layout** — `lantern upgrade` finds documents by their frontmatter id and, when some are not where the current layout puts them, lists the moves and stops. `lantern upgrade --apply` moves them with git (history continues), fixes links that would break and old template names, and makes one commit. It works from any older layout
- **AI tool check** — `lantern doctor` shows, for each installed AI tool, its version (below or above the checked versions), whether its hooks actually run, and hook calls that came without expected fields
- **Obsidian folder and file icons** — with the CSS snippet alone (no plugin), sub-folders and files get icons, and each stage box wraps the whole folder

### Changed
- **Current state folders** — split into `Rules/` (collaboration rules · development principles · work division rules), `Decisions/` (ADRs) and `Deployment and Operations/` (deployment · server operations)
- **Work Unit Log → Work Division Rules** — renamed and moved to `Rules/`
- **Work unit choices** — `/l-plan` recommends new work, add to an existing work, or divide and place, judged by one rule: one work = one purpose. Divide and place shows where each piece goes and why. The 10-task limit is gone, from `/l-task` and the Tasks template too
- **No CLAUDE.md is created** — Claude Code 2.1.277+ reads AGENTS.md itself. An existing CLAUDE.md is kept and only gets `@AGENTS.md` (`@../AGENTS.md` inside `.claude/CLAUDE.md`). `lantern doctor` tells when a CLAUDE.md hides nested AGENTS.md files or a `CLAUDE.local.md` exists
- **Report summary heading** — "3-line summary for the lead" → "3-line summary"

### Fixed
- Documents moved with `lantern legacy adopt` in local mode lost their git history

## [0.1.2] - 2026-10-29

Upgrade: `uv tool upgrade lanternspec`, then `lantern upgrade` in each project (refreshes skills, rules and the AGENTS.md block)

### Added
- **English support** — with `lantern install --language en`, skills, templates, rules, choice names, folder names, command output and generated documents (MOC, reports, debt status, principles …) are all in English. The language is chosen at the first install and stays fixed once it is in `lantern.yaml`
- **Code comment language** — `project.comment_language` (ko | en) in `lantern.yaml` sets the language of code comments apart from the documents; empty follows the document language. `/l-init` asks for it, and the AGENTS.md principles and the principles document follow it
- **Protected sections** — renaming or deleting a section lantern reads or writes (such as "Now" in a log) no longer makes lantern put it back. The feature is skipped and `lantern check` asks whether it was on purpose. Record the answer with the new `lantern sections list|rename|off|on`; the list is in `0. Templates/_meta/Protected Sections.md`

### Changed
- **Install hint** — when the lantern command is missing, `/l-init` and `lantern doctor` suggest `uv tool install lanternspec`, as in the README
- **Keeping documents off the remote** — before running `lantern docs-mode local`, `/l-init` first says in one line that it will commit three settings files to main
- **Output wording** — planning-document IDs left in command output, skills and rules are gone; each place says what it does
- **Noticing questions and ideas** — tech questions and ideas in conversation are also recognized in English ("what is X", "how does X work", "I'd like to" …)

### Fixed
- The Rust and Swift package notes were cut at a comma

## [0.1.1] - 2026-10-28

Upgrade: `uv tool upgrade lanternspec`, then `lantern upgrade` in each project (refreshes skills, AGENTS.md rules and Obsidian settings)

### Added
- **Obsidian vault settings** — opening `docs/` in Obsidian gives a menu that offers only each document type's status, kind and topic choices (Metadata Menu, generated from `enums.yaml`), folder colors per document stage, and callout and quote styles. Existing `.obsidian` settings are kept
- **`lantern obsidian plugins`** — downloads the latest official releases of the recommended plugins (Dataview · Metadata Menu). `/l-init` asks whether to run it. Plugin code and the window layout stay out of git
- **Next steps after install** — `lantern install` tells you the command that opens each AI tool and how to call `/l-init`, and suggests `--tools` when other supported AI tools are on this computer but not set up

### Changed
- **`/l-init` questions** — one decision per question. The knowledge-base question asks only the kind first; path, write mode and topic folder follow separately. Paths and names are offered as found candidates
- **Backend question** — asks "do you write your own server code" instead of "do you need a server" (AWS, GCP or Vercel still count as your own; Supabase or Firebase count as an external service)
- **Project-definition interview** — users and goals are picked from AI-drafted candidates; goals can be left for later (kept as an open question)
- **How the AI talks** — two rules added to the AGENTS.md block: talk to the user in `project.language` (Korean), and never offer an empty "type your own" choice
- **Debt-card "영역" → "주제" (topic)** — only the displayed name changes; the stored key (`area`) and `--area` option stay
- **Names instead of spec IDs** — install output, git hook warnings, agent hook messages, `lantern.yaml` comments and skills no longer show internal IDs such as `H-4~H-10`; they name what is checked instead

### Fixed
- The `/l-init` wrap-up report could come out in English
- The existing-project icon (🏚) overlapped the following text in terminals — replaced with 🏠

## [0.1.0] - 2026-10-27

First release.

### Added
- **`lantern` CLI** — scripts own the format: creating documents (`scaffold`) · issuing IDs · frontmatter · format checks (`check`) · the MOC map (`map`) · reports (`report` · `status`) · checking that docs and code match (`scan` · `sync`) · install checks (`doctor`)
- **13 skills** — `/l-init` · `/l-idea` · `/l-plan` · `/l-design` · `/l-task` · `/l-build` · `/l-learn` · `/l-report` · `/l-template` · `/l-check` · `/l-sync` · `/l-map` · `/l-adr`. One set of skill sources is filled with `lantern.yaml` values and installed for each tool
- **3 AI tools** — installs skills, `AGENTS.md` rules, agent hooks and an MCP server for Claude Code · Codex · Antigravity CLI (`lantern install` · `lantern upgrade`; files you edited are never overwritten)
- **24 document templates** — which documents you get depends on the project (new or existing · team size · screens · server · knowledge base). Template versioning, refining and migration (`template`); status and kind names live in one place, `enums.yaml` (`enums rename`)
- **Work flow** — idea → plan → design (approval gate · DBML · screen mockups) → tasks (dependencies · parallel `[P]`) → build (work branches · worktrees · evidence log · merge into the current state)
- **Managing unfamiliar tech** — knowledge-base connectors (Obsidian · any Markdown folder), a debt ledger (understanding · competency · technical) and an MCP server (`lantern mcp`)
- **Keeping docs and code in line** — git hooks (task IDs · schema-change records · format · document storage mode), agent hooks (session-start summary · format check as soon as a document is written · run log · sync nudge · save progress before compaction · tech-question and idea detection) and GitHub Actions CI (`install --ci`, including per-language tool setup)
- **Document storage modes** — push documents with the code (`shared`) or keep them off the remote (`local`, `docs-mode`)
- **Design principles and code conventions** — design principles chosen from a table by project kind · external integrations · size, and code conventions by language (Python · TypeScript · Swift · Rust · Go) and size, written into `AGENTS.md` and `개발 원칙.md` (`principles`, `lint`)
- **Ways of working and evaluation** — harness · loop · graph recommendation (`harness suggest`); comparing skills · models · settings from the run log (`eval`)

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.10...v0.3.0
[0.2.10]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
