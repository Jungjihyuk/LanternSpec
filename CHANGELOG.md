# Changelog

**English** · [한국어](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.ko.md)

All notable changes to this project are recorded here, version by version.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
