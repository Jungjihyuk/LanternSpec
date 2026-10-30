# Changelog

**English** · [한국어](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.ko.md)

All notable changes to this project are recorded here, version by version.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
