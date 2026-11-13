---
name: l-init
description: Set up LanternSpec for a project — questions picked by the earlier answers decide what kind of project it is (new/existing · team size · project kind · screens · server · knowledge store · design tool), then create lantern.yaml · the docs/ folders · templates · MOC · a draft project definition · development principles · git hooks. Once per project, and again when the project changes (solo → team, adding web …). Use when setting up LanternSpec docs in a project or re-running after the project profile changed.
invocation: manual
argument-hint: "[what changed (when re-running)]"
---

# /l-init — build the document structure that fits this project

**Purpose:** questions picked by the earlier answers decide which documents to turn on or off and which development principles to follow, then build that structure. Every format (files · folders · numbers) is made by `lantern` commands; you ask, judge and fill the blanks.

First check the CLI is there with `lantern --version`. If it isn't, only tell the user how to install it (`uv tool install lanternspec`) and stop.

## 0. First time, or running again?
- **No** `lantern.yaml` → start at step 1.
- **There is one** → go to [Running again](#running-again). Don't ask the questions from the start again.

## 1. Questions — ask one at a time, collect the answers, write them all at once
**How to ask**
- Find out what you can first and use it as the recommended answer: is there code (`git ls-files`) · languages (`lantern principles detect`) · branches (`git branch`).
- **One decision per question.** Don't pack several answers into one question ("and if so, also tell me A and B") — ask for each separately.
- Offer choices so the person only has to pick, and mark the recommended one.
- For answers that must be typed, such as a path or a name, **look for candidates first and offer them as choices**. With 2 or more candidates, add "if none fits, type it in the box at the bottom" to the question. **With one candidate**, ask in a plain message that names it instead of a choice question ("Use X? To use something else, type it"); **with none**, ask in a plain message.
- For a free answer with no candidates (a one-sentence introduction · team member names), ask in a plain message instead of a choice question (AGENTS.md "How to ask").
- Don't create files or run commands as answers come in. **Collect every answer**, then write them all at once in step 2.
<!-- lantern:if tool=claude -->
- Use the question tool (AskUserQuestion) and send **up to 4 questions at a time**. They appear one by one, and the answers come back together.
  - Round 1: questions 1 · 2 · 3
  - Round 2: the follow-up to 3 ("Where will people use it?" allows several answers) · 4 (only when it is asked) · 5 · 6
  - Round 3: question 7, and only what the earlier answers call for — project name · how long it runs · making the repository public · publishing docs · branch flow · (team) member names · (external) API document
  - Round 4: only if a knowledge store was chosen in 5 — the first three questions under "If a knowledge store was chosen"
  - Round 5: then the closed-folder questions — each answer changes the next question, so ask in order
  - Choosing the technologies: each answer changes the next question, so ask in order instead of in a batch
<!-- lantern:endif -->
<!-- lantern:if !tool=claude -->
- Put **only one question** in each message. When you get the answer, go straight to the next question (no summary in between).
<!-- lantern:endif -->

**Questions**
1. 🌱 A new project (greenfield), or 🏠 one with existing code (brownfield)? — recommend brownfield if there is code already
2. How many people? Solo / two or more (team)
3. What are you building? Follow up according to the answer. Offer the choices in these words, and don't show the stored values
   - Service · app — people use it through screens or an API (`--kind service`). Then ask **"Where will people use it? (several allowed)"** Website (`web`) · desktop program (`desktop`) · mobile app (`mobile`) · no screens, API server only (`--clients none`)
   - Tool · library — a CLI, a plugin, or code that goes into other code (`--clients none`). Then ask **"How will it be used?"** CLI tool (`--kind cli`) · library · plugin (`--kind library`)
   - Data · ML — data processing, model training (`--kind data --clients none`)
   - Script · experiment — code you run once or try out (`--kind script --clients none`)
4. Does a server have work to do? (accounts, storing data, calling outside APIs and so on) — if 3 was tool · library or script · experiment, don't ask and use `--server none`. Split by whether *you write* server code, not *where* it runs. Offer the choices in these words, and don't show the stored values
   - Build it yourself — FastAPI, Spring, Express and so on (stored as `custom`: you write the server code, wherever it runs, even if only locally)
   - Use an existing service — Supabase, Firebase and so on (stored as `external`: you don't write server code)
   - Not needed — runs inside the browser or device only (stored as `none`)
5. Do you keep study notes in a knowledge store? None / an Obsidian vault / a plain Markdown folder — ask **only the kind** (path and write mode come below)
6. Design tool? Claude Design / Figma / Canva / none — Claude Design is the Design canvas inside Claude. In Claude Code the AI draws the wireframes itself; in other AI tools, take the screens made in Claude as HTML. Figma and Canva need that tool's MCP server connected to this AI tool (if it isn't, explain how to connect it, and take exported files until then)
7. **Does it connect to outside tools or services?** (AI tools · payments · outside APIs · a structure that takes plugins and so on) — this answer and the project kind from 3 choose the design principles
   - Before asking about languages, find them with `lantern principles detect`. If nothing is found (a new project), decide by the answer to 3
     - A service or app: follow **Choosing the technologies** below
     - Anything else: ask "What will you build it with? Python · TypeScript · Swift · Rust · Go"
   - **Don't ask about size** — lines of code are measured, and team size comes from question 2

**Choosing the technologies** (only for a new service or app) — ask in order after the answers to 1–7
```bash
lantern template show "<<file.tech_criteria>>"
```
- Follow this document's "Decision tree" as written. Ask only the questions in the tree, and don't change its recommendations by your own judgment.
- Use the tree's words for the choices. When proposing a technology, give its pros and cons from "Technology comparison" in one line, and show any alternative with it.
- Put the chosen technologies' languages in `--languages`. Leave out languages `lantern profile write` doesn't accept (Java and so on), and say "LanternSpec doesn't have code rules for this language yet."
- Don't ask about deployment infrastructure or design patterns here. Ask about the development environment (Docker) as the tree says.

**Then ask** (only what the earlier answers call for)
- Project name — when the folder name is the only candidate, ask in a plain message: "Name the project <folder name>? To use another name, type it"
- "Publish the documents to GitHub too?" — offer the choices in these words, and don't show the stored values
  - Yes — they go up with the code (default, stored as `shared`)
  - No — they stay on this computer (stored as `local`: documents stay only on the `docs-local` branch of the same repository. Suits private notes · public repositories)
- "How long will this project run?" — offer the choices in these words, and don't show the stored values
  - A quick try (default, stored as `short`)
  - Run for a long time — with a README · CHANGELOG, and the folder structure decided together (stored as `long`)
- "Will the repository be public for anyone to see? (This is separate from publishing the documents.)" — public / private (default). If public, decide the license next: ask the questions in the "LICENSE" section of `lantern template show "<<file.repo_files>>"` in order, and recommend the license that fits the answers, with the reason. If private, don't ask.
- Branch flow — see "Choosing the branch flow" below
- (if 2 is team) team member names — there are no candidates, so ask in a plain message: "Please list the people working with you, separated by commas"
- (if 4 is external) "Create an API document too?" — if yes, `--extra api`

**If a knowledge store was chosen** (only when 5 is not none, one at a time)
- **Where is it?** — look for candidates first: for Obsidian, folders that contain `.obsidian` (`find ~ -maxdepth 4 -name .obsidian -type d`); for a Markdown folder, near the documents folder. With 2 or more paths found, offer them as choices (up to 3); with one, ask in a plain message "Is this the right path?"; if none are found, ask in a plain message: "What is the path of your notes folder?"
- **How should new notes be made?** — write to the store right away once approved (direct, recommended) / never touch the store, only make draft files (propose_only)
- **(only when the store has folders split by topic) Use those folders as topics too?** (optional) — first skim the store's top-level folders; if there is no folder whose subfolders look like topics (e.g. `2. Study`), **skip this question**. If there is, say what it means first: "Unfamiliar technologies are kept as debt cards, and each card gets one topic (now: backend · frontend · data · ai · infra · other). Your store seems to have folders split by topic — use those names as topics too? This has nothing to do with the project's structure." Offer the folders found and "only the default topics" (recommended).
- **Are there folders in this store the AI must not open?** — offer the choices in these words. For 2 · 3, show the store's top-level folders (leave out hidden ones) and let the person pick several. If the folders don't all fit in the choices, list them in a plain message and have the person type the names.
  - No. Leave everything open
  - Yes. Pick the folders to close (`knowledge.deny`)
  - Open only a few. Pick the folders to open (`knowledge.allow`)
- **(only when a folder is closed and this is macOS) Also stop the AI tool from opening those folders directly?** — offer the choices in these words. For 1, add to the closing message: "From now on, start the AI tool with `lantern guard -- <tool command>` (e.g. `lantern guard -- claude`)". Off macOS, don't ask; say in one line: "Stopping the AI tool from opening them directly works on macOS only for now."
  - Stop it. From now on start with `lantern guard -- claude` instead of `claude`. Claude Code's own sandbox has to be off
  - Don't stop it. Only lantern's search · read skip the closed folders

**Choosing the branch flow** — **a command decides** the recommendation and the choices to offer (pass the answers to 1 · 2):
```bash
lantern work flow --team solo|team --origin greenfield|brownfield
```
Show only its `Choices` and mark its `Recommended`. Don't swap in your own judgment. The person may still pick another. If `Choices` is just A, don't ask: use A, and say in one line that it can be changed by running `/l-init` again after connecting GitHub. `default branch` below means the branch the command names.
Question: "How should finished work be merged? You can change this later." Keep the choices in plain words, and when offering B · C add "A PR is a request to review the changes on GitHub before they are merged":
- **A. Keep it simple** — finished work goes straight into the default branch. Good when you're new to this or building fast on your own.
- **B. Separate development from deployment** — work merges into dev, and goes to the default branch through a PR when you deploy. Good for a service that deploys as soon as the default branch changes.
- **C. A PR for each work** — each work is reviewed through a PR, then merged. Good if you get code reviews.
- **D. Keep what you use now** — branches stay as they are; only where work merges is recorded. (Show the existing branches with it)

After the choice, ask more only when needed:
- **B:** if `dev` doesn't exist, "Create a `dev` branch?" (if not, let them choose again)
- **C:** if both `main` · `dev` exist, "Which one should work merge into?"
- **D:** "Where does finished work merge?" (existing branches as choices) · "Does merging need a PR?" Then say: "LanternSpec only takes care of work up to that merge. Deploy the way you do now."
- **B · C · D:** "Is there a naming rule for work branches?" — no (recommended: named automatically, like `work/W-012`) / yes. If existing branches show a pattern, offer it (e.g. `feature/JS-15-normalization` → `feature/{ticket}-{slug}`). `{id}` is filled with the work ID; the other blanks are chosen per work. Without `{id}`, works on different branches may get the same number, so recommend including it.

Profile values (`--deploy` only for B, `--branch` only with a rule):
| Choice | `--base` | `--pr` | `--deploy` |
|---|---|---|---|
| A | default branch | `none` | |
| B | `dev` | `deploy` | default branch |
| C | the chosen branch (else the default branch) | `work` | |
| D | the answered branch | `work` · `none` from the answer | |

If an answer is unclear, ask again instead of guessing. Once everything is collected, show a summary of the answers and go to step 2.

## 2. Write the profile → work out which documents turn on (scripts)
```bash
lantern profile write --language en --name "<name>" --origin greenfield|brownfield --team solo|team [--members "Ana,Ben"] \
  --clients web,mobile --server none|external|custom [--extra api] \
  [--knowledge "<knowledge store path>" --knowledge-type obsidian|folder --knowledge-write direct|propose_only [--areas-from "2. Study"]] \
  --design claude-design|figma|canva|none --remote shared|local --base main --pr none|deploy|work [--deploy main] [--branch "feature/{id}-{slug}"] \
  --kind script|cli|library|service|data --external yes|no [--languages python,typescript] --lifespan short|long
lantern profile set "knowledge.deny=[4. Work]"   # only when folders to close were picked (for folders to open: knowledge.allow=[…])
lantern principles detect --write   # record code size · languages · check commands (build.format · lint · typecheck)
lantern principles show             # the chosen design principles · code conventions
lantern scaffold init --plan        # the folders · documents it would create (creates nothing yet)
```
Tell the user the `principles show` result in a line or two (e.g. "CLI tool · external integrations → single responsibility and extension points are Must; Python uses ruff · pyright").

**Parts (each folder its own rules):** a part is a sub-project inside the repository — a folder with its own language and check commands.
`lantern parts` lists the sub-folders with their own package file (`pyproject.toml` · `package.json` …, e.g. `backend` · `frontend/apps/web`) as candidates.
With **two or more**, ask about all of them at once, each with its evidence — "Make this folder a part?" — then `lantern parts add <folder>` · `lantern parts ignore <folder>` as answered.
Two or more parts each get their own `AGENTS.md` (that language's conventions · that folder's check commands), and the root AGENTS.md keeps a map of the parts. With one candidate or none, don't ask.

**Tool settings files:**
- 🏠 brownfield: settings `detect` finds **already in use are only recorded** — don't change settings files (`pyproject.toml` · `.eslintrc` …) or suggest switching tools. For a tool in the conventions that has no settings, only ask "add it?".
- 🌱 greenfield: **ask** whether to add the convention's tools as dev dependencies (e.g. `uv add --dev ruff pyright` · `pnpm add -D @biomejs/biome typescript`) and create their settings (e.g. `[tool.ruff]` · `[tool.pyright]` in `pyproject.toml`), and **do it once approved**. They must be dev dependencies so CI installs the same tools. If declined, clear them with `lantern profile set build.lint= build.typecheck=`.
Briefly show the user the `--plan` result (e.g. "mobile → a platform-integration and a deployment document will be created").

If the knowledge store has `--areas-from`, read its folders with `lantern knowledge areas` and **only suggest** which to add to the **debt-card topics** (default: backend · frontend · data · ai · infra · other).
- Say what is being chosen first: "These are folder names found in your store. Pick the ones to add as debt-card topics. They are used to see, in the debt status, how many unfamiliar technologies have piled up per topic (this has nothing to do with the project structure or where notes are saved)."
- Leave out folders that overlap the defaults (e.g. AI Engineering → ai) and say why in one line. Always offer "only the default topics".
- Put only what the user picked into `area` in `docs/<<folder.templates>>/_meta/enums.yaml` (after the scaffold in step 3).

## 3. Build the structure
- If `local` was chosen, **first** `lantern docs-mode local` (an empty docs branch · `.gitignore` · `.ignore` · a hook that blocks pushing, all at once)
  Before running it, tell the user in one line: "Switching to keeping documents off the remote, this commits 3 settings files to main (`.gitignore` · `.ignore` · `lantern.yaml`)."
- 🏠 brownfield with an existing `docs/`: **first** `lantern legacy adopt` (moves the existing documents to `docs/<<folder.legacy>>/` with `git mv` — their history continues)
- If B was chosen and `dev` is to be created, `git branch dev` (after the first commit if there is none yet). Ask the person again before pushing it. Don't create or change any other branch.
- Then `lantern scaffold init`
- Finally `lantern upgrade` — the skills were installed before these answers, so remake them to carry the chosen settings (the branch flow and so on).
- If technologies were chosen, write them in the parts section of `<<file.architecture>>` and ask "This is hard to undo. Record why with `/l-adr`?"
- For a project run for a long time (`long`) with technologies chosen, show 2–3 folder structure candidates that fit them, following "Folder structure" in `<<folder.rules>>/<<file.repo_files>>`, and decide together. Record the decision with `/l-adr`.
- If the repository is to be public, create `LICENSE` from the chosen license's standard full text (fill in only the year and the copyright holder). Don't write the text from memory; if unsure, get the official text from the person.

## 4. 🌱 Greenfield — a short interview for the draft project definition
Ask the three `<<marker.required>>` blanks of `docs/<<folder.current>>/<<file.project_definition>>` **in order**. Build each next blank's candidates from the answers before it, so the person only picks or edits.
1. **One-sentence introduction** — there are no candidates, so ask in a **plain message** instead of the question tool, with one example: "Please introduce this project in one sentence. (e.g. a budget app I used alone, now shared with friends)"
2. **Main users and their problem** — offer 2–3 candidates built from the introduction.
3. **Goals** — from the introduction and users, offer **3–4 checkable goal candidates** and let them pick several (e.g. "after inviting a friend, the expenses spent together show on one screen"). If it's too early to decide, they can pick **"decide later"**.

- Fill the blanks with the chosen answers. Leave "decide later" and unknown blanks as `<<marker.unknown>>` — they stay among the open questions in `lantern status` and won't be forgotten.
- Optional blanks may stay empty.

## 5. 🏠 Brownfield — fill in → link → ask about blanks
1. **Fill in:** read the code (what exists: facts) + `<<folder.legacy>>/` (why: background) and fill drafts of `<<folder.current>>` — architecture · feature list · data · (if any) API.
   - Data: if there are SQL migrations, `lantern dbml from-sql <migrations folder> --out "docs/<<folder.current>>/<<folder.data>>/schema.dbml"` → `lantern dbml render`. **The migrations and the real database are the reference.**
   - In each current-state document's frontmatter, record the related code and when it was checked: `lantern meta set "<document>" 'code=[src/auth, src/api]' checked_commit=$(git rev-parse --short HEAD)`
2. **Link:** add a `Source: [[<<folder.legacy>>/…]]` link to everything you filled in.
3. **Legacy map:** in the `<<folder.legacy>>/<<file.legacy_map>>` table, fill in for each document what it covers · whether it is still true · route · new place. You recommend the route; the user only confirms:
   - 🧽 Absorb — still true → only the essentials into `<<folder.current>>`, with a source link
   - 🗄 Archive — past records (meeting notes · old plans · finished work) → link only
   - 🚚 Move — documents that stay in use → when wanted, `/l-template migrate "<<folder.legacy>>/….md"`
4. **Ask about blanks:** required blanks only · if you can guess, ask "is this right?" · group the questions for one document · "don't know" becomes `<<marker.unknown>>`.
5. **Bonus:** gather TODOs · "later" items from the existing documents with `lantern legacy todos` and show them as idea candidates. Record only the ones the user picks, with `/l-idea`.
<!-- lantern:if tool=claude -->
6. **Design system** (when Claude Design was chosen as the design tool and the project has screens): if the code has shared UI parts such as buttons, inputs and colors, mention it once.
   "If you move the existing buttons, colors and fonts into a Claude design system, new screen mockups come out looking like the current app. If you'd like that, run `/design-sync`."
   The person runs it. If they don't, carry on with the next steps as usual.
<!-- lantern:endif -->

## 6. git hooks · CI · Obsidian
"Install git hooks that check task IDs · schema records · document formats at commit time? (they only warn by default)" → if yes, `lantern hooks install`.
For a team, ask once more: "Block from the start?" → if yes, `lantern profile set git.hooks=block`.
(Structural mistakes — the document storage rules — are always blocked, whatever this value is.)

If `git remote -v` shows github.com, ask next: "Check on GitHub too? On every push, GitHub runs the document checks · lint · type check · tests for you and on PRs it also checks the title and commits for work IDs (CI)." → if yes, `lantern install --ci`.
Then ask: "Add a commit message template? It shows the type and work ID format when you run `git commit` yourself." → if yes, `lantern install --commit-template` (each person needs to run it once).
If the branch flow is C, also ask: "Add a template for PRs opened on the GitHub site?" → if yes, `lantern install --pr-template` (a template already there stays).
The workflow includes the setup steps for this project's languages (installing uv · pnpm …). To turn it off later, `lantern install --no-ci`.

Then ask: "Download the recommended plugins for viewing documents in Obsidian (Dataview · Metadata Menu)? The menus for choosing statuses and kinds, and the task display, work right away." (recommended: yes) → if yes, `lantern obsidian plugins`.
- The downloaded plugin code is not committed to git (`docs/.obsidian/.gitignore`). Team members get it with the same command.
- If the download fails (no internet …), don't stop with an error; say they can install the two plugins from Obsidian's community plugins instead.

## 7. Work-mode suggestion · common wrap-up
Tell the user, one line per axis, which build mode (loop scope · task delegation · parallel works) fits the project size, from `lantern build-mode suggest`; if they want it, `--apply` (changes only the loop scope), then `lantern upgrade`.
```bash
lantern close l-init
```
Fix any ✖ errors in the check result, and say which ⚠ required blanks remain. End with a 3-line report: what was created · blanks left · next step (`/l-idea` or `/l-plan`; for brownfield, `/l-idea` after reviewing where things stand).

---

## Running again
1. Show the previous answers with `lantern profile show` and ask only **"has anything changed?"**
2. Change what changed with `lantern profile set key=value …` (e.g. `project.team=team 'project.members=[Ana, Ben]'`, `'project.clients=[mobile, web]'`).
3. With `lantern scaffold init --plan`, **first say which documents would turn on** and check: "Adding web creates sections for web screens and web deployment. Add it?"
4. Ask only the questions the added documents need (see "to ask" in the `--plan` output: web → how it deploys, team → member names).
5. `lantern scaffold init` — creates only new documents and leaves existing ones alone. Documents no longer needed aren't deleted; they are marked "<<current_status.inactive>>". If an existing document needs a section for a new kind (e.g. `## Web`), add it to that document.
6. Don't change the document storage mode (shared ↔ local) here → `lantern docs-mode local|shared`.
   To change the branch flow, change the values in the table above like `lantern profile set git.base=dev git.pr=deploy git.deploy=main` (the naming rule is `git.branch`), then `lantern upgrade`. Works in progress keep their branches.
7. If skill behavior values such as `idea.capture`, or the project kind (`project.kind` · `project.external` · `project.languages`) changed, `lantern upgrade` (re-creates the skills · the development principles in AGENTS.md · the development-principles document).
8. Common wrap-up: `lantern close l-init`.
