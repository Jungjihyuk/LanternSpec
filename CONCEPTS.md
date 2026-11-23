**English** · [한국어](CONCEPTS.ko.md)

# LanternSpec Concepts

A guide for people new to LanternSpec. It explains, with examples, what the words you'll meet in its documents and commands refer to and why they exist.
If this is your first time, read "The big picture" first, and look up the rest when a word comes up.

This guide covers LanternSpec's own words. Your project's business terms go in `Glossary.md` inside the project.

## The big picture

LanternSpec helps you build with AI so that **what you built and why stays written down**.
An idea like "I want a sign-in feature" goes through five steps before it becomes working code.

| Step | What you do | Example: sign-in | What it leaves |
|---|---|---|---|
| 1. Idea | Jot down a thought | "Sign-in would be nice" | An idea card |
| 2. Plan | Decide what to build, why, and when it counts as done | "Sign in with email and password" | `Plan.md` |
| 3. Design | Decide how to build it | "Remember the sign-in with a session cookie" | `Design.md` |
| 4. Tasks | Split it into pieces you can check one at a time | "① users table ② sign-in API ③ sign-in screen" | `Tasks.md` |
| 5. Build | Write the code, test it, save it | Build the tasks in order and commit | `Log.md` (evidence) |

You run each step from your AI tool with a command (a skill) starting with `/l-`, such as `/l-idea` or `/l-plan`. Each step leaves a document, so later you can look back and answer "why did we build it this way?"

## 1. How LanternSpec is laid out

LanternSpec's features sit in three layers. The split keeps the main line steady as features are added.

### Core flow
> The five steps above, together with `/l-init` that prepares a project, are the core flow — LanternSpec's backbone.
> You can build from start to finish with it alone, without any other feature.

### Choice point
> A place in the core flow **where you can choose how something is done**. For example, you can choose whether screen mockups are made in Claude, Figma or Canva.
> If the chosen tool is missing or fails, the flow doesn't stop: it falls back to asking a person for help.

- Examples: the screen mockup tool, how built screens are checked, your study notes store, how often building stops for checks, whether to build several works at once

### Add-on
> A feature that is handy but **that the core flow doesn't need**.

- Examples: progress reports, the ledger of unfamiliar technologies, AI work evaluation, the build mode suggestion, bringing another tool's documents over

## 2. The five steps

### Idea
> Jotting down a thought so it isn't lost. Nothing has been decided yet, so write it freely.

- Example: "It would be nice to stay signed in for longer"
- Where to look: `/l-idea` · `docs/1. Ideas/`

### Plan
> Deciding **what** to build and **why**. Here you also decide "what has to be true for this to be done" — these are the acceptance criteria.

- Example: "With the right email and password you're signed in; with a wrong one, an error message shows"
- Where to look: `/l-plan` · `Plan.md` in the work folder

### Design
> Deciding **how** to build it. Only the parts that change this time are written: program structure, screens, data. A person checks and approves it before building starts.

- Example: "Remember sign-ins with sessions, and store passwords encrypted in the users table"
- Where to look: `/l-design` · `Design.md` in the work folder

### Tasks
> Breaking the design into **pieces small enough to check one at a time**, along with which must come first.

- Example: "① create the users table → ② build the sign-in API → ③ build the sign-in screen"
- Where to look: `/l-task` · `Tasks.md` in the work folder

### Build
> The AI turns the tasks into code in order, tests them, and saves (commits) them one by one. Instead of saying "done", it leaves evidence of what changed and which tests passed.

- Where to look: `/l-build`

### Wrap-up
> Tidying up after the build: merging the code into the project's main line, bringing the documents that describe the whole project up to date, and moving the finished work folder to the archive.

- Where to look: the last step of `/l-build`, or `/l-finish` if you built several works at once

## 3. Documents

Everything LanternSpec writes lives in the `docs/` folder.

### Work
> **One unit of building** a feature or change. Each work gets its own folder and a number like `W-001`. Its plan, design, tasks and log documents live in that folder.

- Example: `docs/2. Work/W-001 Sign-in/`

### Current state
> Documents that describe **what the program is like right now**: the feature list, program structure, data, screens and so on. They're updated whenever a work finishes, so they're always current.

- How it differs from work documents: a work document says "what we meant to do then"; the current state says "how it is now".
- Where to look: `docs/3. Current State/`

### Decision record (ADR)
> When you make a choice that's hard to undo, this records **what was chosen and why**. It answers "why did we do this?" months later.

- Example: "Sign-ins are kept as sessions, not JWTs, because signing out must end them right away."
- Where to look: `/l-adr` · `docs/3. Current State/Decisions/`

### Log
> **A diary for one work**: which code changed, which tests passed, what was tried and failed, and where things stand now. When a conversation with the AI gets long and its beginning is about to be summarized, progress is saved here automatically.

- Where to look: `Log.md` in the work folder

### Archive
> Where finished work folders are moved, so they don't mix with works in progress.

- Where to look: `docs/2. Work/Archive/`

### Bringing another tool's documents over
> **Moving the documents another tool left in a consistent format into LanternSpec's folders and templates.** For now this moves OpenSpec.

- A finished change becomes an archived work, a change in progress a work, and one not yet decided an idea.
- Content with no matching section is not deleted; it is gathered under "Not moved" at the bottom of the document. The originals are kept in `5. Legacy Docs/`.
- Documents without a consistent format are not moved. Read them and move only what is needed, one at a time.
- Where to look: `/l-migrate` · `lantern migrate openspec`

### Rule documents
> Documents about **what the project has agreed to follow now**: development principles, the criteria for choosing technologies, how to write files like `.gitignore`, the project glossary, the design system and so on.

- The design system: the colors · type · spacing · shared parts every screen follows. Only projects with screens get it, and `/l-design` reads it before making screen mockups. What differs per screen is drawn in the work's `Design.md`.

- Where to look: `docs/3. Current State/Rules/`

### Template
> **The blank form** for every document. A new document copies the form and only fills in its blanks, so documents look the same whoever made them.

- Where to look: `docs/0. Templates/`

### Protected section
> A section LanternSpec reads and writes automatically (for example "Now" in a log). If you rename or remove one, LanternSpec asks a person first whether to keep using that feature.

## 4. Checks

### Acceptance criteria
> "What has to be true for this to be done", written as **sentences you can check**. They're numbered `AC-1`, `AC-2` and so on, and they decide whether building is finished.

- Good: "With a wrong password, 'Email or password doesn't match' shows"
- Avoid: "Sign-in works well" (you can't check what "well" means)
- **Tying a test:** if a test checks the criterion, tie it on at the end of the line: `[test:: tests/test_login.py::test_wrong_password]`. The tied test is what the automatic loop is judged by.

### Design approval
> **The gate where a person checks the design** before building starts. It stops a lot of code from being written in the wrong direction. It can be set to let small designs through without asking.

### Understanding mark
> A note saved with an approval: **"did I follow it?"** When planning ends and when a design is approved, the person picks "go ahead, I follow it" or "go ahead, handing it over", and the answer is kept in the document's `understood` property (`yes` · `no`). Handing it over never blocks anything. But when a work marked that way was built by an automatic loop (judged by the run log, not by the setting), one understanding-debt card is made, and `/l-finish` lets the person pick which to pay back.

### Current-state approval
> When a work finishes, before the "current state" documents change, a **summary of what will change is shown for confirmation**. Big changes such as data structures or APIs are always asked about, whatever the setting.

### Evidence
> **Proof** the AI leaves instead of just saying "it's done": changed files, the tests run and their results, the acceptance criteria checked, and commit numbers, written in the log.

### Screen check
> When a task that builds a screen is done, the AI **opens the screen itself, captures it** and checks that it shows, wraps and scrolls properly and responds when pressed. It works in AI tools that can control a browser.

- Whether it matches the mockup is for a person to decide: the capture and the mockup are shown side by side.
- Setting: `verify.browser` in `lantern.yaml` (`auto` · `none` · the name of a skill or MCP you want to use)

### Waiting for a person
> The mark left when the AI can't check a screen itself (no browser control, or it failed). Work carries on, and the checks are gathered and confirmed by a person before merging.

- Example: `Waiting for a person: terms /terms — run the server, open http://localhost:8000/terms, check the line breaks (AC-2)`
- Until a person confirms, that acceptance criterion stays unchecked, so an unchecked screen isn't merged.

### Needs answer
> Instead of filling in something unknown with a guess, it's marked `❓ Needs answer`. A task with this mark doesn't start until a person answers.

## 5. Ways of building

### Loop scope
> **How often the AI stops to have a person check** while building. Choose one of two:

- **Check each task:** test and report as each task finishes. Suits first-time use and small projects.
- **Loop automatically:** after all tasks, the AI keeps fixing things on its own until every acceptance test passes. Suits projects with automated tests in place.
- Setting: `build.loop` in `lantern.yaml` · get a suggestion: `lantern build-mode suggest`

### Loop eligibility
> The condition that decides **whether a work may run in the automatic loop**. Every acceptance criterion of the work needs a committed test tied to it, and a test command (`build.test`) must exist. Without eligibility the work goes on with a check after each task even when `build.loop: on`, and the criteria missing a test are named.

### Loop record
> **What happened in an automatic loop isn't said by the AI; `lantern loop` measures it and writes it to the run log.** `loop start` fixes the settings, the base commit and the number of tests before the loop; `loop attempt` runs one criterion's test and judges by its exit code; `loop finish` runs the whole suite and the "invalid pass" check below to end a round. When one criterion fails `build.same_ac_limit` times in a row, or the rounds reach `build.loop_limit`, the loop stops and every later try or round command is refused. Starting another loop for the same work needs the person's say (`--again`), and the restart is shown as a ⚠ at archive. Later steps such as the understanding-debt card read this record, not the setting in `lantern.yaml`.

### Invalid pass
> The device that **catches a pass reached by changing the tests**. If, after a loop starts, a linked test file or a test settings file listed in `build.test_config` changes, or fewer tests run in the whole-suite run, the pass doesn't count and the work goes to the person. Writing new tests in new files is fine (adding to a linked file voids the pass). Edits aren't blocked: a fingerprint of the files is kept when the loop starts, and what changed is caught. The number of tests is compared only in a round whose suite passed.

### AI retro
> A record kept each time an automatic loop ends: **one line for every acceptance criterion (or check) that did not pass on its first try**. One file per month (`2026-11.md`) in `4. Operations/AI Retro/`. The point is to pile up what got blocked and see whether the same weakness keeps coming back, so the harness can be fixed.

- **The fact fields** (time · work · tries · result · run) are written by lantern from the run log. A criterion that passed at once leaves no line; one that passed after several tries leaves one (`[tries:: 3] [result:: Passed]`); one that never did and stopped leaves `[result:: Stopped]`. A check that isn't a criterion (a failed whole suite · an invalid pass) is kept as `[check:: …]`.
- **The judgment fields** (weakness · remedy · hypothesis · suggestion) are filled by the AI with `lantern retro judge`. The weakness (spec · context · harness · model · verification · environment) and the remedy (LanternSpec · harness settings · model choice · connected tool · planning habit) accept only the values of the lists in `enums.yaml`.
- **Confirmation** is a person's: once a week, `lantern retro review` shows the unconfirmed lines and `lantern retro confirm` marks the ones that are right. The summary at the top is rewritten by lantern each time a line is added or confirmed.
- A loop judged by the whole suite only (`build.test_one` empty) makes no line per criterion.

### Review after the build
> A step where **a reviewer in a fresh context looks once more** at a build that passed its tests. Tests check only what was written down, so a weak test, a build that strays from the design or a breach of the development principles survives a pass. With `build.review: on`, one review is made after the acceptance-criteria tests all pass and before applying to the current state (not after each task).

- **The review pack (rubric):** `lantern review pack` gathers it from the documents — for each acceptance criterion "does the build satisfy it", the fixed item "does the test really check the criterion", the design · development principles · repository file rules (an item whose document is missing is left out), the code changes since the work started, and the test result.
- **The reviewer's independence:** it gets neither the build conversation, nor the builder's explanation, nor the tries — only the pack. Even the same model in a separate context removes a good part of the bias.
- **The verdict:** `Pass` or `Issue` (ground `file:line`) for each item. Code reads the reviewer's own lines into the run log; the builder doesn't retell it. When there are issues the build is fixed and reviewed again up to `build.review_limit` times, the rounds are counted by the command, and what is left goes to the person. When there were issues, a `[check:: Review]` row is added to the AI retro.
- **Who runs it, on which model:** the harness does. Claude Code gets a `lantern-reviewer` sub-agent definition and uses `build.review_model` as its model (empty: the tool's own). For Codex and Antigravity, `lantern review pack --tool …` prints the command that starts a fresh context.
- Settings: `build.review` (off · on) · `build.review_limit` (default 1) · `build.review_model`.

### Task delegation
> Within one work, the AI hands **tasks that don't depend on each other** to several helper AIs (sub-agents) — like a person splitting a job among teammates. Tasks that can run at the same time are marked `[P]`.

- Only in AI tools that have this ability.

### Parallel works
> Building **several works at the same time**. For example, open two terminals and build a "terms page" in one and a "server health API" in the other.

- How it differs from task delegation: delegation happens **inside one work**; parallel works are **several works**.
- Steps: check with `/l-parallel` before starting that nothing needs deciding together → run `/l-build` in each terminal → when all are done, merge with `/l-finish`

### Worktree
> **Another copy of the same project laid out in a different folder.** With parallel works, each work gets its own folder so they don't touch each other's files. Saves (commits) all go into the same project.

### Base branch · base folder
> The **base branch** is the project's main line where finished works are merged (usually `main`). The **base folder** is the original project folder where the base branch is open. Even when works run in parallel, merging and tidying happen in the base folder.

### Work branch
> **A side path** used while building one work (for example `work/W-001`). You work without affecting the main line, then merge into the base branch when done.

## 6. Learning what you don't know

### Understanding debt
> **Technology the AI used that you don't really understand yet.** Leaving it would make it hard to touch when something breaks, so it's written in a ledger like a debt to pay back.

- Example: the AI used an encryption method called `argon2` for sign-in, and you'd never heard of it
- Where to look: `/l-learn` · `docs/📒 Debt/`

### Debt card
> A card for one piece of understanding debt. It finds and links related notes in your notes store, and is marked "resolved" once you've studied it.

### Known tech
> The list of technologies you already know well. They're not suggested as understanding debt again.

### Knowledge store
> Where you keep your study notes (Obsidian, a plain Markdown folder, Notion). Once connected, LanternSpec checks it for notes you've already written whenever it meets an unfamiliar technology.

- **Notion is searched by title and properties.** Notion's own search looks at titles only, so the list of the connected pages (title · address · property values) is fetched whole and searched here. A name that is not in a title but in a property such as `Type` is found too, and the result says which property matched. A word only the body has is not found yet.
- The fetched list is kept in the project's `.lantern/` for 10 minutes (a personal record, never committed). A search that finds nothing fetches the list once more and looks again, so a note made a moment ago isn't missed.
- Obsidian and folder stores read the files directly and find the body and tags, so they don't use this list.
- **One command guides the Notion connection:** run `lantern knowledge setup notion` **yourself in a terminal**. It walks through making the integration, which permissions to turn on (just read content for drafts only, read and insert content for writing), the token and connecting pages, shows whether the token works and how many pages the integration sees, and saves the settings in `lantern.yaml`.
- **The token is taken without the AI seeing it.** On macOS the Keychain tool (`security`) asks for it itself, so it never becomes an argument of a command or enters lantern's memory, and the adapter looks in the environment variable and then the Keychain. On other systems the command points to the environment variable `NOTION_TOKEN`. If the AI tries to read it from a shell it can't be stopped, so the real defense is **the pages connected to the integration** (only those can be seen).

### Open and closed folders
> The folders of the knowledge store the AI **may and may not open**. You list them in `lantern.yaml` under `knowledge.allow` (only these are open) or `knowledge.deny` (these are never opened). Notes in closed folders don't turn up in search, reading or writing.

- Example: keep study notes (`2. Study`) open and work records (`4. Work`) closed

### Guarded run
> Starting the AI tool **inside the operating system's sandbox** (`lantern guard -- claude`). The operating system keeps the tool out of the closed folders whatever way it tries to open them. Works on macOS and Linux (Linux needs bubblewrap).

- Stopped: every way the AI tool opens files itself (reading files, running commands, scripts)
- Not stopped: an AI tool started without the guarded run, and going through other programs that are already running

### Domain knowledge
> Reference material on **what must be followed in your field**, such as laws, company policies and business rules. Once a person adds it, the AI reads just the relevant part when needed.

- Where to look: `docs/📚 Domain Knowledge/` · `/l-domain`

## 7. Settings

### lantern.yaml
> The one file holding **the project settings people chose**. Your answers in `/l-init` are saved here, and you can change them later.

- View: `lantern profile show` · change: `lantern profile set key=value`

### Document mode
> Whether documents go to GitHub **with the code** (`shared`) or **stay on your computer** (`local`). Choose `local` for private notes, or when the code is public but the documents shouldn't be.

- Setting: `docs.remote` in `lantern.yaml` · switch: `lantern docs-mode`

### Document auto-commit
> Whether the plan, design and tasks steps **save (commit) just their work's documents automatically** when they finish. The default is automatic (`auto`); choose `manual` to check and save them yourself.

- Setting: `docs.commit` in `lantern.yaml`

### Project lifespan
> Whether this is **a quick try or a project you'll run for a long time**. For a long-running one, the README and changelog (CHANGELOG) are set up properly and the folder structure is decided with a person at the start.

- Setting: `project.lifespan` in `lantern.yaml` (`short` · `long`)

### Components
> What was **added to the AI tool** when it started: the names of its MCP servers, plugins, skills you put there and hook events are written to the run log when a conversation (session) starts.

- Only names are kept, never a command, an address or a variable. The tool's settings files are read; nothing is run.
- `lantern eval` shows, for each component, in how many sessions it was there and how often its MCP tools were called, and tells what was added or dropped between sessions. Calls are counted for **MCP tools only**, so the table has one line for each MCP server and plugin, while skills and hook events are only counted in one line (the names are in `lantern eval --json`). 0 calls only means "not used in the recorded sessions", not that it isn't needed. Turns of a session that has no component list (from before the lists were kept, or logged by another version of lantern) can't have their calls counted, so how many there are is told separately.
- MCP tool calls that **ran and failed** are counted in their own column (a call the person refused or cancelled is not counted as a failure). A server that is connected but only fails shows up. The `PostToolUseFailure` hook writes this, so an existing project gets the new hook with `lantern upgrade`.
- For now it is read from Claude Code only (other tools show nothing). Plugins built into the tool are not in a settings file, so they are not listed.
- Whether to add or drop one is up to a person. lantern only shows the facts and never changes the AI tool's settings.

### Component card
> A document, one per component you added, that holds **why it was added, what you expect, what to measure and when to look again**. Make it with `lantern scaffold component "<name>" --kind mcp`; it appears in the decisions folder as `CMP-001 …`.

- Its parts are: what · why (the problem) · expected effect · measure · cost · review time · review result. What to measure is picked from: number of calls · time taken · tokens · check errors · retro lines · review findings.
- The status (`status`) is watching · keep · dropped. **A person** writes the review result and changes the status then.
- When a conversation starts and there is an MCP server or plugin that wasn't there before, the AI is told once, so that it asks the user whether to leave a card. The first conversation only takes stock of what is already there and asks nothing, and skills and hooks are not asked about. A component that already has a card is not asked about.
- A card is not required. The component log and `lantern eval` work without one.

---

If you're changing LanternSpec itself, also see [`RATIONALE.md`](RATIONALE.md), which records why the flow, folders and rules are the way they are, and [`GLOSSARY.md`](GLOSSARY.md), which lists where names in the code overlap.
