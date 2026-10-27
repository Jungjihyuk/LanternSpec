# Changelog

**English** · [한국어](https://github.com/Jungjihyuk/LanternSpec/blob/main/CHANGELOG.ko.md)

All notable changes to this project are recorded here, version by version.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/Jungjihyuk/LanternSpec/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jungjihyuk/LanternSpec/releases/tag/v0.1.0
