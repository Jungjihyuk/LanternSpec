---
id: CUR-repo-files
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: Repository File Rules
template_version: 1.0.0
based_on: 1.0.0
---
# 📘 Repository File Rules

> [!abstract] At a glance
> The format to follow when **first creating** `.gitignore` · `docker-compose.yml` · README · CHANGELOG · LICENSE · the folder structure.
> The first format sets the pattern for later changes, so make it easy to read from the start.
> For a file that already exists, keep its format and put new entries in the matching group.

## Common comment rules
- **Header block:** at the top of the file, say what it is for, how it is grouped, and the commands people use often.
- **Groups:** number them and separate them with divider lines, in the order the header block gives.
- **Subgroups:** inside a group, split with a one-line `##` heading.
- **Reason comments:** for a line whose value isn't obvious, add the reason at the end of the line. Don't restate what the name already says.
- **New entries:** put them in the matching group, not at the bottom. If none fits, make a new group and add it to the header block.

## .gitignore
Group by **"who or what creates it"**. Leave out groups the project doesn't have.

```gitignore
# ============================================================
# .gitignore grouping: "who/what creates it"
# ============================================================
# 1. Environment   — made by the development environment (OS, editors, logs)
# 2. Build         — build output
# 3. Toolchain     — made by language tools (virtual environments, caches)
# 4. Data          — databases · data files
# 5. AI Tools      — made by AI tools (only when their settings aren't committed)
# 6. Infra         — environment variables, secrets, deployment
# 7. Documentation — internal documents, drafts
# ============================================================


# ========================= 1. Environment ===========================

## OS - macOS
.DS_Store

## IDE / Editor
.idea/
.vscode/

## Logs
*.log


# ========================= 3. Toolchain =============================

## Python
__pycache__/
.venv/


# ========================= 6. Infra =================================

## Environment Variables
.env
.env.*.local    # commit .env.example (the list of values needed)
```

## docker-compose.yml
```yaml
# =============================================================================
# <project> Docker Compose for development
#
# Services:
#   db        - PostgreSQL (development DB · test DB)
#   backend   - API server
#   frontend  - web screen development server
#
# First time: cp .env.example .env
# Run:        docker compose up -d
# Often used: (migrations · test account · tests)
# =============================================================================

# Fix the name so every folder (worktree) uses the same containers and volumes
name: <project>

services:
  # ---------------------------------------------------------------------------
  # DB - PostgreSQL
  # Say what the service is for and what is created on first start.
  # ---------------------------------------------------------------------------
  db:
    image: postgres:18
    ports:
      - "5434:5432"    # host 5434 → container 5432 (avoids a clash with a local DB)
    env_file:
      - .env

volumes:
  db-data:
```
- Give each service a divider block: its role on the first line, then why it is set up this way.
- Pin versions instead of `latest`.
- Keep secret values in `.env` and write only variable names in compose.

## README
Pick the level by `project.lifespan` in `lantern.yaml`.

**A quick try (`short`)**
1. Title and one-line introduction
2. How to run it (requirements · commands)

**Run for a long time (`long`)**
1. Centered header: title · one-line introduction · badges (platform · language · license · release)
2. A one-line quote on what the project is
3. Why it was made
4. At a glance (one picture or table)
5. Features (a `###` and a short description for each)
6. Installation (use it right away / build from source)
7. Usage
8. Contributing (details in `CONTRIBUTING.md`)
9. License

- Use one emoji per section heading at most, and none in the body.
- Put warnings and cautions in a `> ⚠️` quote block.

## CHANGELOG
For projects run for a long time (`long`).

```markdown
# Changelog

All notable changes to <project> are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **What changed, in one sentence.** A short explanation if needed.
  - Why it was done this way, and what to watch out for.

### Changed

### Fixed
```
- Use only Added · Changed · Fixed, and remove the empty ones.
- Record only what users notice. Leave internal clean-ups out.

## LICENSE
Decide it only when the repository is made public. This table is a summary to help choose, not legal advice.

| Kind | License | What it means |
|---|---|---|
| Permissive | MIT | Keep the copyright notice and you may use, change and redistribute freely, commercially too |
| Permissive | Apache-2.0 | MIT plus an explicit patent grant, ending it for anyone who sues over patents |
| Permissive | BSD-3-Clause | Like MIT, and forbids using the names to promote derived work |
| Weak copyleft | MPL-2.0 | Only changed files must be published |
| Weak copyleft | LGPL-3.0 | Only changes to the library must be published; programs using it can stay closed |
| Strong copyleft | GPL-3.0 | When distributed, the whole derived work must be published under the same license |
| Strong copyleft | AGPL-3.0 | GPL-3.0, and the source must be published even when offered as a network service |
| Source-available (not open source) | BSL · SSPL | The source is visible, but commercial use and the like are limited |
| Proprietary | none | Write "All rights reserved" in the README instead of a LICENSE file |

**Choose by questions** — ask them in order from the top.
```text
1. Should code others change also have to be published?
   ├─ No  → 2. Are patents a concern? (a company · a field with patents)
   │          ├─ Yes → Apache-2.0
   │          └─ No  → MIT
   └─ Yes → 3. Should it be published even when only offered as a service (no installer handed out)?
              ├─ Yes → AGPL-3.0
              └─ No  → GPL-3.0
4. (When publishing is required) Do you want companies that won't publish to pay to use it separately?
   └─ Yes → dual licensing (below)
```

**Dual licensing** — offering the same code under two terms at once.
- Under the open source license (usually AGPL-3.0) it's free but the source must be published; whoever won't publish buys a paid commercial license.
- The stronger the duty to publish, the stronger the reason to buy, so it's often paired with AGPL-3.0.
- **Only the copyright holder can do it.** Code from outside contributors belongs to them, so get a CLA (contributor license agreement) before accepting contributions.
- Put the open source license's full text in LICENSE, and say in the README how to ask about the commercial license.

- Use the license's standard full text in LICENSE, filling in only the year and the copyright holder.
- Check it fits the licenses of the libraries used (e.g. a project using a GPL library can't be released as MIT).

## Folder structure
- **A quick try (`short`):** follow the default structure of the chosen technologies.
- **Run for a long time (`long`):** show the person 2–3 candidates that fit the chosen technologies and decide together (e.g. separate `backend/` · `frontend/`, folders by feature, a single app). Record the chosen structure in an ADR and the architecture document.
- When adding a new top-level folder, note why in one line in the architecture document.

<!-- lantern:template-only -->
## Change log
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-09 | Base template |
