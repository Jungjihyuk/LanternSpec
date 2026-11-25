**English** · [한국어](RATIONALE.ko.md)

# LanternSpec Design Rationale

For people changing LanternSpec itself. It records **why** the flow, folders, formats and decision rules are the way they are, and **which alternatives were turned down and why**.
Read the matching section before changing something, and update this document along with the change.

| Document | Covers | Read by |
|---|---|---|
| [`CONCEPTS.md`](CONCEPTS.md) | What words mean | People new to LanternSpec |
| This document | Why things were decided | People changing LanternSpec |
| A project's `3. Current State/Rules/` documents | The rules to follow | Each project's people and AI |
| [`AGENTS.md`](AGENTS.md) | Rules for changing this repository's code | People and AI changing LanternSpec |

The content of a rule (its tables and numbers) is written once, in the rules document's template. This document gives only the reasons and points to that template, so a changed rule never needs two edits.

## 1. The flow

### Five steps (idea → plan → design → tasks → build)
- **Decided:** a thought goes through five steps before it becomes code, and each step leaves a document.
- **Why:** AI builds fast but doesn't leave behind why it built things that way. Separate steps give a person a point to check at each one, and let the reasons be traced later.
  - The plan says **what · why**, the design says **how**. Mixed together, "what we meant to change" and "which way we chose" can't be told apart, and changing only the method shakes the purpose too.
  - Tasks split the design into **pieces that can be checked one at a time**. Each piece leaves a commit and evidence, so a fault can be narrowed down.
- **Turned down:** one document for plan and design. Fewer documents, but one approval point disappears and design approval reopens the purpose itself.

### Core flow · choice points · add-ons
- **Decided:** features sit in three layers. The core flow works end to end on its own, a choice point hands over to a person when it fails, and an add-on can be removed.
- **Why:** as features grow, the flow easily gets tied to one tool or add-on. Deciding the layer first gives a test for whether a new feature would block the flow.
- **Source:** "Core flow and add-ons" in [`AGENTS.md`](AGENTS.md)

### What we build and what we leave to other tools
- **Decided:** LanternSpec builds only the features whose source is LanternSpec's own documents, and connects to other tools for the rest. For example, the document-code drift check is built in, while isolated execution, handing work out to several agents, and a screen for watching agents are left to other tools.
- **Why:** LanternSpec's value is that the documents are the reference. Adding an execution engine or a monitoring screen does not make that value grow, and those areas are changing fast in the hands of large teams, so a one-person project following them only adds upkeep. On the other hand only LanternSpec knows the specs, so checks that come from the specs cannot be left to another tool.
- **Turned down:**
  - **Putting every needed feature inside:** fewer tools to install, but the bigger the feature set, the more the overall structure shakes. Lantern Harness, built earlier, went this way, its structure shook, and it ended up unused.
  - **Making only the documents and leaving every check to other tools:** other tools do not know LanternSpec's specs, so the drift check and acceptance criteria checks cannot be handed over.
- **Source:** "Core flow and add-ons" in [`AGENTS.md`](AGENTS.md)

### Design approval
- **Decided:** a person approves the design before building.
- **Why:** AI writes a lot of code quickly in the wrong direction too. Stopping at the design is far cheaper than turning around after the code is written.

### Understanding mark
- **Decided:** approval and understanding are different questions, so they are asked together but not as a new step: at the places that already ask (the end of planning, the design approval). The answer is kept in one document as `understood: yes · no`, and a work handed over without being followed leaves one understanding-debt card when an automatic loop built it (the run log shows the loop ran).
- **Why:** a person may approve without following in order to move fast. Blocking that kills the speed; not recording it loses, later, the fact that this code was left wholly to the AI. A tag plus a debt lets speed and understanding be managed together.
  - A small design that skips the approval isn't asked, so it follows the plan's mark.
  - A technology known only in part inside a document stays with the debt cards, as before.
- **Rejected alternatives:**
  - Blocking the automatic loop without the mark. It stops a person who can't keep up from pushing ahead, which is against the purpose.
  - Marking understanding per acceptance criterion. It is the most precise, but far too much to mark while planning.

### The facts of an automatic loop are measured by code (`lantern loop`) · loop eligibility · invalid pass
- **Decided:**
  - An acceptance-criterion line can carry a field that ties a test (`[test:: …]`). Only a work whose every criterion has a committed test may run the automatic loop (loop eligibility); any other goes on with a check after each task.
  - The facts of the loop (start · tries · round results) aren't the AI's report: `lantern loop` runs the test command itself and writes the result **by exit code** to the run log. The settings and the base commit at the start are fixed in that line, and the steps after it (the understanding-debt card · the warning at archive) read this record, not the setting in `lantern.yaml`. The setting is the intent, the record is the fact, and when they differ a `⚠` says so.
  - When a loop starts, the content of the linked test files and of the files `build.test_config` points at (paths or patterns) is fingerprinted into the start line; when a round ends and at archive, the same function compares them. A changed, new, moved or deleted file, or fewer tests in a round whose suite passed, makes the pass invalid and sends the work to the person. It compares content, not git, so a git failure or a settings file in `.gitignore` lets nothing through. What remains: a new settings file not listed in `build.test_config` (a new `conftest.py`, say) can't be told from a new test, so list it as a pattern.
  - When one criterion fails `build.same_ac_limit` times in a row, or a round hits its limit or is invalid, every try and round command for that work is refused. Starting another loop for the same work needs the person's say (`--again`), and the restart shows as a ⚠ at archive. The AI isn't expected to stop on its own.
  - With `build.test_one` empty nothing is judged per criterion: a failing whole suite may come from other criteria not built yet, so it isn't counted as this criterion's failure and no limit applies.
- **Why:** an automatic loop is weakest the moment it trusts the AI saying "it passed". Weakening a test to make it pass is easy for an AI to do without any bad intent, and guessing "did it loop?" from a setting turns every later judgment wrong when the setting and the reality differ. Putting the making of facts in one place of code, and letting the rest read only that record, gets safety and speed together (a git comparison and reading the record take milliseconds; only the tests that had to run anyway run).
- **Rejected alternatives:**
  - Blocking edits to test files from the start (hook · sandbox). It doesn't fit the contract that an agent hook never stops the agent, and it blocks writing new tests too. Catching what changed blocks less legitimate work. `lantern guard` protects the closed folders of the knowledge store, so it isn't widened.
  - Reading each test tool's output to find per-criterion passes. Trusting one exit code keeps working when a tool changes. Only the number of tests is read from the summary line of a few tools; when it can't be read, just that check is skipped.
  - Letting the AI write the try records. Whoever writes becomes whoever judges.
  - Signing the run log to tell lines the AI edited by hand. The gain is small for the cost; it stops at warning when the record is missing or differs from the setting.

### The review after the build is by a reviewer in a fresh context, and code reads the verdict into the log (`lantern review`)
- **Decided:**
  - With `build.review: on`, one review is made after the acceptance-criteria tests all pass and before applying to the current state. It is `off` by default, and `lantern build-mode suggest` recommends `on` for a project that uses the automatic loop. When a review can't be made (the tool can't start a fresh context) it goes to the person — the core flow runs without a review (a choice point).
  - The rubric is gathered from the documents by script (the review pack). The build conversation, the builder's explanation and the tries are left out. When the change is too big (120,000 characters), it is put in from the front and the remaining files are only named, for the reviewer to read itself.
  - The verdict is read by code from the reviewer's own `- [Pass|Issue] item` lines (counted by lines, not by the reviewer's closing line). For Claude Code a hook records the answer when the sub-agent stops; other tools get the answer into a file and record it with `lantern review record`. The round limit (`build.review_limit`) is counted by `lantern review pack`, which makes no pack and hands the work to the person when no round is left. An issue without a `file:line` ground is counted in the record.
  - Each sub-agent call leaves its name · start · end · model · tokens in the run log (`SubagentStart` · `SubagentStop`), and a session start leaves a hash of the sub-agent definition files it reads. Which combination of build and review models is efficient is decided from this record, not from a general rule.
  - The model isn't fixed in the definition file but taken from `build.review_model`. Only the sub-agents of LanternSpec's flow (the reviewer) are installed; general sub-agents belong to the person's harness settings repository.
- **Why:** tests check only what was written down. A weakly written test slips past both the tests and the invalid-pass catch. A builder that reviews itself shares its blind spots and is kind to its own output, so the review sees only the documents and the changes, in a fresh context. And if the builder retold the verdict it could change, so code reads the reviewer's lines as they are.
- **Rejected alternatives:**
  - **The building agent reviews itself.** Same context, same blind spots.
  - **Judging by the tests alone.** Weak tests, drift from the design and breaches of the principles slip through.
  - **An execution engine where LanternSpec picks the model and starts the agents.** The harness and executors already do that, and it changes fast. Only the connection points (definition file · command · hook) are provided.
  - **Review by people only.** It doesn't fit the automatic loop's aim of easing the human bottleneck. People focus on the issues left and on confirming the retro.
  - **Reading the reviewer's closing line (`Verdict: …`).** A closing line that disagrees with the items would go unnoticed. Only the item lines are read, and code counts.
- **What was checked and what wasn't:** Claude Code's sub-agent definition (`.claude/agents/<name>.md`) and the input of `SubagentStart` · `SubagentStop` were checked against its docs; the fresh-context options of Codex (`codex exec --ephemeral -s read-only -m … -o …`) and Antigravity (`agy --print --sandbox --model …`) against `--help`. That a reviewer really runs in a live session and its verdict gets recorded has not been checked yet. A sub-agent's transcript is written asynchronously, so its tokens may come up a little short. The reviewer's definition disallows `Edit`, `Write` and `NotebookEdit` but leaves `Bash` (it has to run `git diff` and the tests), so that it writes no file through the shell rests on its instructions; and a builder writing the verdict itself with `lantern review record` isn't blocked either, only shown as a ⚠ at archive.

## 2. Where documents live

### Why `2. Work` and `3. Current State` are separate
- **Decided:** work documents (plan · design · tasks · log) live in the work's folder; what the program is like now lives in `3. Current State`, which changes only when a work finishes, after approval.
- **Why:** work documents say "what we meant to do then"; the current state says "how it is now". Kept together, ongoing plans and the real state mix, and the AI reads features not yet built as existing.

### Finished works go to the archive
- **Why:** so only works in progress stand out, while the record of finished ones is kept, not deleted.
- **With parallel works:** a work another running work links to is archived later, so its paths don't change while another worktree reads its documents.

### Moving existing documents shows a preview first (`lantern legacy adopt`)
- **Decided:** `lantern legacy adopt` only shows move · keep and the reason for each item; it moves with `--apply`. The move uses `git mv` and leaves one commit. Four things stay — what LanternSpec made, what `docs.keep` in `lantern.yaml` lists, what a script · setting · code file outside the documents folder uses by path, and GitHub Pages files.
- **Why:** a documents folder holds more than documents. Moving a file a script reads by a fixed path, such as an update feed, breaks the release. A person should see the list before the move, and one `git revert` should undo a wrong one.
- **"Ours" by a mark, not by name:** a folder counts as made by LanternSpec only when `0. Templates/_meta/enums.yaml` exists, the MOC only when its frontmatter has `template`. Leaving an older template folder or MOC that merely shares the name mixes it with the new templates, and `lantern map` would rewrite someone else's file.
- **Turned down:** moving right away and letting the person check `git status`. With hundreds of staged changes, the one wrong move is hard to find.
- **Source:** `src/lanternspec/check/legacy.py`


### Another tool's documents become works and ideas (`lantern migrate openspec`)
- **Decided:** OpenSpec's archived changes become finished works in `2. Work/Archive/`, its open changes works in `2. Work/`, and those that are only a note ideas in `1. Ideas/`. The sections of `proposal.md` · `design.md` · `tasks.md` go into the matching sections of `Plan` · `Design` · `Tasks` (`resources/openspec.yaml`); content with no matching section is gathered under "Not moved". The originals are kept in `5. Legacy Docs/openspec/`. It previews by default, and `--apply` leaves one commit.
- **Why:** when an existing project's past and ongoing work stay in another folder and format, the board, the reports and the next task cannot see them. OpenSpec has a proposal · design · tasks per change, the same shape as our works, so they are moved as works rather than reduced to a summary.
- **The command does the conversion:** an AI rewriting the documents could change what they say. The command only moves sections; the skill (`/l-migrate`) only has the person confirm where the open changes go.
- **A finished work is not asked planning questions:** `lantern check` does not ask the tasks of a finished work for a size or a link to an acceptance criterion. Past work brought over has neither, and finished work is not planned any more. Works in progress are still asked.
- **Documents without a consistent format:** not moved automatically; they stay in `5. Legacy Docs/`. Only what a person reads and picks is moved, one at a time, with `/l-template migrate`.
- **Turned down:** writing the past as one summary document by period. The shape of the original documents (what · why · how · tasks) is lost, and work in progress cannot be continued.
- **Source:** `src/lanternspec/check/openspec.py`, `src/lanternspec/resources/openspec.yaml`

### AI Context Files are a section of the Repository File Rules
- **Decided:** the reference for the files an AI tool reads by itself lives in the "AI Context Files" section of `Repository File Rules`. Every table has the same three columns — file · who defined it · what goes in it — in the order standard · LanternSpec · (existing projects only) before · after.
- **Why:** an existing project already has an `AGENTS.md` · `CLAUDE.md` or the files of another workflow tool. With the standard and what LanternSpec uses written down first, how to fit the files that were there and where another tool's documents go are decided by the same reference. Keeping before · after tells someone who joins later what changed and why.
- **What the standard table lists:** only what a large organization defined and many places use. `llms.txt` (for websites) and old formats (`.cursorrules`) are left out.
- **Turned down:** a separate rules document. Like the README and `.gitignore`, this is "the format of files kept in the repository", so one document is easier to find.
- **Source:** `src/lanternspec/resources/locales/<language>/templates/Repository File Rules.md`

### The rules folder (`3. Current State/Rules/`)
- **Decided:** the rules a project follows (development principles · tech selection criteria · repository file rules · task breakdown rules …) live as documents in the rules folder, and skills read and follow them.
- **Why:** a rule kept only inside a skill's text is hard for people to find and impossible for a team to change. As a document, a rule the team changed is followed by the AI too.
- **Turned down:** writing the rules into skills. Skills are regenerated on `lantern upgrade`, and the team's edits would be lost.
- **Criteria for opening features (CLI · REST API · MCP):** how a feature you make is opened is a technology choice too, so it is in the tech selection criteria. `/l-init` doesn't ask it; `/l-adr` uses it as a basis. MCP isn't conditioned only on "no shell": AI tools with a shell use design apps and company databases over MCP. Whether to attach someone else's MCP to an AI tool is how the harness is made up, not the product's technology, so the component card covers it.

### The design system is a document in the rules folder (`Rules/Design System.md`)
- **Decided:** the colors · type · spacing · corners · shared parts every screen follows are written in `3. Current State/Rules/Design System.md`. Only projects with screens get it, and `/l-design` reads it before making screen mockups. Its sections come in the order of the standard `DESIGN.md` (Google Labs) — overview · colors · typography · layout · elevation · shapes · components · do's and don'ts.
- **Why:** when each work only draws its own mockups, colors and type drift from screen to screen. This is "what we follow now", so it belongs in the rules folder next to the development principles and the technology criteria, where people find it and skills read it the same way.
- **When a `DESIGN.md` already exists:** that file is the reference and this document only links it. The same value is not written in two places.
- **Turned down:** ① the domain knowledge folder — that is for reference material brought in from outside and read only when needed, unlike a standard to follow every time. ② creating a `DESIGN.md` at the repository root — the format is still a draft and may change, and outside the documents folder people don't see it. With the sections in the same order, moving to it later is easy.
- **Source:** `src/lanternspec/resources/locales/<language>/templates/Design System.md`

### The AI retro lives in `4. Operations`; code writes the facts, and the judgment stays inside the lists (`lantern retro`)
- **Decided:**
  - For each acceptance criterion (or check) that did not pass on its first try, one line goes into `4. Operations/AI Retro/YYYY-MM.md`. A criterion that fails several times still gets one line, written once, when the loop **ends** (`loop finish` and the try that hits the limit call it; if the retro fails the loop does not stop).
  - The fact fields (time · work · tries · result · run ID) are computed by code from the run log; the judgment fields (weakness · remedy · hypothesis · suggestion) are filled by the AI with `lantern retro judge`. That command **refuses, as it writes**, a value that is not in the lists of `enums.yaml` (`retro_weakness` · `retro_remedy`), and `lantern check` catches, once more, a value outside the lists, an unknown field or half a judgment in a hand-edited file.
  - What the AI got stuck on while building is written with `lantern retro note`, loop or not. It shares the file but has its own field (`[stuck:: …]`), and no tries or result, since nothing measured it. The debt ledger takes only what a person asked or chose (`lantern debt --by`); it refuses an AI's name and points to this command.
  - A person confirms once a week. Writing the judgment again clears the confirmation. The summary is rewritten by code whenever a line changes.
- **Why:** the values of a retro exist to count "does the same weakness pile up", and names that vary can't be counted. Stopping a wrong value at the moment of writing leaves the AI no way to slip, which beats finding it later with a check. Facts the AI would write from memory can be wrong (tries · times · run IDs), so they are read from the run log. A retro is "what happened then", so it goes to the operations record, not the current state.
- **Rejected alternatives:**
  - **Keeping it in `3. Current State`.** Current state keeps today's facts in one place; a retro only piles up as history.
  - **A table.** The same reason the task list isn't a table: when a column is missing, a value lands in another column with no warning.
  - **The AI writing the whole retro.** It can write facts such as versions, times and tries wrongly, and its diagnosis of a cause shares its own blind spots. So the hypothesis is one line from checked facts, and a person confirms.
  - **Gathering it from loop records only.** A project with no loop got no line at all, and what blocks outside an acceptance criterion (how a tool or library behaves) had nowhere to go, so it ended up as understanding-debt cards.
  - **Only a "who got stuck" field on the card.** What a person doesn't know and what the AI got stuck on are paid back differently (study · fixing the harness). Mixed in one ledger, the person's debt looks larger than it is.
  - **One file per work.** The same weakness scatters across files and the repetition stays hidden. A month is a good size for a weekly check.
  - **A line per try.** A line is complete only with the final result and the number of tries. The detail of each try is found by the run ID in the run log.

## 3. Formats

### One task per line (`- [ ] W-001-T01 What [size:: 1h] [ac:: AC-1]`)
- **Why:**
  - It is a checkbox, so it can be ticked in Obsidian and on GitHub.
  - Every value carries its name (`size::`), so its meaning survives a change of order or a missing value, and an AI's slip shows.
  - `lantern` commands change a single line, with little risk of touching other tasks.
- **Turned down:**
  - **A table:** aligned columns read well, but Obsidian can't tick a checkbox inside a table out of the box. And a value's column is set only by its position, so if an AI leaves one cell out, the next value lands in the wrong column without a warning.
  - **Attributes on sub-lines under each task:** readable in other editors too, but one task becomes several lines and commands and checks get complicated.
- **Instead:** in Obsidian a CSS snippet (`report/obsidian.py`) shows each line as a table row. The file stays as it is.

### Names of statuses, kinds and sizes live in `enums.yaml`
- **Why:** names written separately in code, skills and templates have to be hunted down for every change. Code finds them by role, not by name, so a team can rename them and nothing breaks.
- **Source:** "Single source" in [`AGENTS.md`](AGENTS.md)

### One idea template per kind, with two tables (when recorded · afterwards)
- **Decided:** Each idea kind (feature · improvement · bug · experiment · tech review) has its own template. Each has a table filled in when the idea is recorded and one filled in afterwards (result · improvement result · cause and fix · conclusion), and cells with a fixed choice list their options. `/l-build` fills the afterwards table when it applies the work to the current state. A kind with no template of its own uses the plain `Idea` template.
- **Why:** Each kind needs different questions (a bug needs steps to reproduce, a tech review needs candidates compared). When cards of one kind share the same rows, reading them together shows what was added and what was tried and failed. Without the afterwards table a card keeps only the wish, and there is nothing to look at when the same bug or experiment comes back.
- **Turned down:**
  - **One template with every kind's cells:** most cells would go unused, which makes it hard to read.
  - **Keeping the outcome only in the work documents:** works move to the archive and one work mixes several things, so a bug's cause or an experiment's result can't be read by kind. The card holds a line or two and links the work documents.
  - **Putting bug type · verdict values in the frontmatter:** each value would add an `enums.yaml` list and a check. For now they are found by the fixed row names in the tables.

## 4. Decision rules

The content of each rule is in its rules document template (`src/lanternspec/resources/locales/<language>/templates/`).

### Task size (`15m · 1h · 4h · 8h`) — [Task Breakdown Rules](src/lanternspec/resources/locales/en/templates/Task%20Breakdown%20Rules.md)
- **Decided:** a size is **the hours a person would put into it, added up**, even when spread over days. Anything bigger than `8h` is split. It is a step on a scale, not a promise.
- **Why:**
  - The time the AI actually took had almost nothing to do with size. In a test project a task that would take a person a day (a sign-in API) took one minute, and an hour-or-two task (setting up the screen's foundation) took twenty. What takes an AI long is waiting, not difficulty.
  - A size in human terms moves with **the effort a person needs to review and understand** the work. The bigger the task, the more there is to review.
  - Work bigger than `8h` is hard to review, and when it gets stuck you find out late.
- **Labels:** **the name is the time.** `S · M · L` needed explaining. The next try, `half` · `1d`, needed "how many hours is 1d" defined separately in the code (8 hours), and that hidden definition put the timeline out of step, drawing `1h` as three hours. `4h` · `8h` define themselves. Obsidian's Dataview shows all four as durations in the app's language.
- **Turned down:**
  - **Sizing by the AI's actual time:** as above, it doesn't reflect the size of the work.
  - **Story points (1 · 2 · 3 · 5 · 8):** every team means something different by them, so their meaning doesn't carry for a solo developer or a new team.
  - **Names in days such as `half` · `1d`:** they need the hidden conversion described under "Labels".
- **Source of the hours:** `SIZE_HOURS` in `core/taskfile.py`, the names turned into numbers. The only place a size becomes dates is the due date suggestion (`lantern task estimate`), which divides by the working hours a day a person sets (`--hours`).

### Where an unknown goes — same document
- **Decided:** unknowns fall into four kinds. A question unrelated to the work becomes an idea; a choice that can be settled by weighing it up is decided in design (ADR); what can only be learned by trying becomes a spike task; what only a person can answer gets `❓ Needs answer`.
- **Why:** with every unknown in one place, things that could be settled quickly get pushed to "research later", or the AI fills them with guesses. Placing each by its nature makes clear who resolves what, at which step.

### Spike tasks (`[spike]`)
- **Decided:** what can only be learned by trying becomes a task whose size is its time limit. Its conclusion goes in an ADR or the work's `Log.md`, and its trial code is not reused as is.
- **Why:** as a task it is handled in order by `/l-build` and shows on the timeline and as a checkbox. The flow gains no new step and no new kind of document.
- **Turned down:**
  - **A separate research document:** a new kind of document and template would widen the core flow's formats.
  - **An idea card:** it would slide into "someday", losing its link to the work it is blocking.

### Parallel works (`/l-parallel` → `/l-finish`)
- **Decided:** before several works start at once, what they must decide together is checked; `/l-build` in each worktree does only its own tasks; merging, the current-state update and archiving happen once, by `/l-finish` in the base folder.
- **Why:** in testing, two works each chose a sign-in method (sessions · JWT), and a session in the base folder edited another work's documents. When documents several works share are changed in one place only, they don't get mixed.
- **Turned down:** agents talking to each other to agree. Tools support it differently, and what was agreed isn't left in a document.

### Screen check
- **Decided:** when a screen task is done, the AI opens it in a browser, captures it and checks the functional acceptance criteria. If it can't, it leaves "waiting for a person" and carries on. Whether it matches the mockup is a person's call.
- **Why:** if the screen check stopped the work, every parallel work would wait for a person. The checks left over are gathered and asked before merging.

### Drawing the timeline
- **Decided:** the time axis holds **only real times**: when work was actually done, and dates a person planned. Only stretches with work get fine columns (5 minutes to an hour); an hour or more without any task is folded and labelled like "⋯ 5 h ⋯". A finished task shows how long it took as text. Tasks not started and without a date wait in a "no date yet" column on the right with their size; dragging one onto a day plans it. A work's row has one bar per stage: planning, design and splitting into tasks are drawn from the time their skill actually ran (the skill time in the run log), the build from its tasks' times. A bar's color names its stage; task bars take the build's color, a solid fill when finished and stripes while in progress. Who did a task shows on hover and is not a color. On a day chart, stages that fall on the same day split that day between them, side by side in stage order.
- **Why:**
  - AI work comes in bursts with long gaps. Drawn by days, minute-long tasks pile into one column; drawn by hours, most of the chart is empty.
  - A size says how much work, not when. Putting undated tasks on the axis with a length guessed from their size needed a conversion like "hours in a day", and that guess even changed the column size.
  - It should show where a work spent its time. One span for the whole work can't tell the time spent planning and designing from the time spent building. A stage's time counts only the time the AI worked, not the waits for the person.
  - A color reads only when it means one thing. When the same bar's color says both the stage and who did it, people read it as a third status. Who is on a task now is for the kanban, which answers "where is it stuck now".
- **Turned down:**
  - Estimated bars chaining unstarted tasks by order and size. They ignored nights and weekends, looking like overnight work, and on a day chart `1h` filled a whole day. For a forecast, `lantern task estimate` suggests dates and skips weekends.
  - A bracket (├──┤) over the whole work's span. It showed only when the work started and ended, not which stage took the time in between.
  - Coloring task bars by who did them (person · person + AI · AI). It covered the done and in-progress colors, so there seemed to be three statuses.
  - Coloring finished tasks green like the kanban. On the timeline, which stage a task belongs to matters more, so tasks keep the build's color and a solid fill or stripes tell done from in progress.
  - Drawing stages on top of each other on a day chart. Planning, design and splitting into tasks done on one day hid under each other and under the build bar.
- **Only recorded times are shown:** `lantern task start · done` stamp times from the computer's clock. The document keeps minutes and the run log (`task` lines of `.lantern/runs.jsonl`) keeps seconds, which are used when the two agree. When the document was changed by hand or there is no run log, the document's times are used. Less than a minute is said as "under 1 min", and a task with only a date, or finished without being started, has no length shown.
  - At first a task that ended in the minute it began was drawn as ending 30 minutes later. A value meant to make the bar visible looked like a real time, and a task that took less than a minute seemed to end at a time still to come. How narrow a bar may be is for the drawing side (the plugin) to decide.
  - `lantern check` reports a time in the future or a finish before its start, which only a hand-written value can be. Times are in the time zone they were written in, so up to a day is let pass (a time written in Seoul is also checked by CI in UTC).
- **Source:** `src/lanternspec/resources/obsidian/lantern-timeline/main.js`; stage times from `tools/runlog.py` (skill time); data from `report/views.py`

### Kanban
- **Decided:** works appear as cards in stage columns (plan · design · tasks · build · done), and clicking a card opens that work's tasks in a window. It is read only.
- **Why:**
  - The timeline answers "what was done when", the kanban "where is each work held up now". They answer different questions, so both stay instead of making people pick one.
  - Stage columns are more useful than three columns (not started · in progress · done). LanternSpec works pass stages by waiting for a person's check, so the column where cards pile up shows what is held back.
  - Cards aren't dragged to change a stage. Skills move stages through checks like design approval, and `/l-build` checks tasks off as it leaves tests and evidence; changing them on screen would skip those checks.
- **Turned down:** adding a kanban view to the Lantern Timeline plugin. The timeline and the kanban change for different reasons, so one plugin would mean touching one to change the other. As two plugins, a view nobody wants can be turned off in Obsidian's settings.
- **Source:** `src/lanternspec/resources/obsidian/lantern-kanban/`; the data comes from `report/views.py`

### Notion fetches the list of pages and searches titles and properties here (`learn/knowledge/notion.py`)
- **Decided:** Notion's search API looks at titles only, so the list of the connected pages (title · address · edit date · property values) is fetched, 100 at a time to the end with no search term, and searched here. A title equal to the name scores 100, one containing it 60, a property value equal to it 50 and one containing it 30, and each alias after the first name scores one less. The summary of a result says which property matched (`Type: Grafana`). The fetched list is kept in `.lantern/knowledge-notion.json` for 10 minutes.
- **Why:**
  - A note's category and tags are often in properties, and the list response already carries them. In a real workspace (445 pages) the whole list took 5 requests · about 5 seconds, and the terms found out of six went from 2 to 4 (Prometheus and Grafana were only in a `Type` property).
  - The body costs dozens of requests per page, so reading all of them is estimated to take hours and is left out for now. Whether a body index is needed is decided after this search has been used.
  - The list is kept for a while. Searching with one list instead of asking for each name (the name and its aliases) separately would cost 5 seconds per search without it.
  - When nothing is found the list is fetched once more and searched again, unless it was fetched within the last 30 seconds. That keeps a note made a moment ago from being judged missing, without repeating 5 seconds when several terms in a row have no note.
  - The titles and properties in the list are a personal record, so they go in the state folder and in its git-ignore list. If the folder can't be written to or the file is broken, no list is kept and the search just runs.
  - The deciding part (`match`) is a pure function, so it is tested without files or network.
- **Limits:** a word only the body has is not found (Pydantic · Starlette). A note made a moment ago takes tens of seconds for Notion to put into its search. Values of different properties score the same.
- **Turned down:**
  - **Calling Notion's search for each name.** It only sees titles.
  - **Refreshing only what changed.** A page that was deleted or unshared can't be noticed.
  - **Searching through the official Notion MCP.** It has no way to narrow what it reaches, and its results don't fit this contract (`lantern knowledge`) as they are.
- **Source:** `src/lanternspec/learn/knowledge/notion.py` (`listed` · `match` · `NotionAdapter.search`)

### Notion is only added to, and a database gets a row that fits its properties (`learn/knowledge/notion_database.py`)
- **Decided:** when `knowledge.path` is a page a new note becomes a page under it, and when it is a database a new row. Which one it is isn't a setting: Notion is asked. The values of a row's properties are written in the draft's `properties` and approved with the note, and are checked against the database's properties and choices both when the draft is made and when it is written. A note with the same title in that place is refused, and is made again only under another title the person decides.
- **Why:**
  - For someone who keeps notes in a database, notes piling up under a page are of no use. A row with empty properties also drops out of filters and views.
  - Never changing an existing page limits the reach, so that the AI can't change what it shouldn't. A new page can simply be deleted, but a change is hard to take back.
  - Sending Notion a choice that isn't there adds the choice to the database. That goes against the promise not to change another store's structure, so it is refused first.
  - Whether a title is taken is asked when writing, not looked up in a list that may be ten minutes old. Case and surrounding spaces don't make another title.
- **Limits:** only the titles in the place new notes go (right under the page, or in that database) are looked at. Formula, relation, people and file properties are not filled, database templates are not applied, and a database with several data sources is refused.
- **Turned down:**
  - **Adding (2) to the title by itself.** Duplicates would pile up quietly next to the note that is there.
  - **Default values in `lantern.yaml`.** The values differ from note to note, and there would be one more place to change with the properties.
- **Source:** `src/lanternspec/learn/knowledge/notion_database.py` (properties), `src/lanternspec/learn/knowledge/notion.py` (`NotionAdapter.write`)

### The store takes care of a note's form — in Notion it is written as blocks (`learn/knowledge/notion_markdown.py`)
- **Decided:** a draft is one Markdown text (with Obsidian's callouts and wikilinks), and each store's adapter writes it in its own form. Obsidian and folders store it as it is; Notion gets blocks and looks. Only the Notion adapter calls the conversion, so what is stored in Obsidian is not affected by it.
- **Why:**
  - At first only headings, lists and quotes were converted, so in a real note `**bold**`, `` `code` ``, `[!abstract]` and numbers showed as text and code had lost its language.
  - Having drafts written in a different form for each store would let the AI get the form wrong, and they would look broken where drafts are read (Obsidian). Code converts the same way every time.
  - What the API doesn't take (more than two levels of nesting, more than 100 items, long text) is moved right after or divided, never dropped.
  - The code languages and limits were checked by asking with a parent page that does not exist (404 when the form is right, 400 when it is not, and nothing is made). An emoji counts as two characters.
- **Limits:** wikilinks, links inside the vault and attached images become text. A folded callout is written open, and a numbered list that starts in the middle keeps its numbers as text (Notion counts from 1 again). From the fourth level on, list items stand at the third.
- **Turned down:**
  - **A Markdown library.** It doesn't know Obsidian's callouts, wikilinks and highlights, and the standard doesn't see `**bold(x)**` as bold before a Korean particle. It would also be one more runtime dependency.
  - **Having the skill write drafts for the store.** Easy to get wrong, for the reasons above.
- **Source:** `src/lanternspec/learn/knowledge/notion_markdown.py`

### One command guides the Notion connection, and the Keychain takes the token itself (`lantern knowledge setup notion`)
- **Decided:** one command that the person runs in a terminal guides these steps: ask how notes are written · guide making the integration (it opens the integrations page in the browser) · tell which permissions to turn on · take the token · check that Notion accepts it and how many pages the integration sees · check the page or database new notes are made in · save `lantern.yaml`. When there is no `lantern.yaml` it stops before asking for the token and has `/l-init` done first. `/l-init` points to this command once `lantern.yaml` is made and before the documents and skills are, and checks `lantern.yaml` instead of taking "it's done" for an answer. It saves only after every step has worked, so stopping part way leaves `lantern.yaml` as it was.
- **lantern never receives the token:** on macOS it runs `security add-generic-password -U … -w` (with `-w` last and no value) attached to the terminal, and the Keychain tool asks for the input itself. The token never becomes a command argument, nor enters lantern's memory or a log. The adapter looks in the Keychain (service = the name of the token's environment variable, account = the user) and then the environment variable, so people who put the item in with `security` and people who only used a variable (nothing in the Keychain) both keep working.
- **Why:**
  - A token that enters a conversation with the AI stays in its record. A command that asks for a token has to be run by the person, and refuses to run without a terminal.
  - With the Keychain, an AI tool opened from somewhere other than a terminal and a hook read the same token without an environment variable line.
  - The permissions are guided to the minimum for how notes are written (read content for drafts only, read and insert for writing). Update content, comments, user information and agent features, which the adapter doesn't use, are turned off.
  - At the end it shows how many pages the integration can see and the titles edited most recently. The pages connected to the integration set what can be read, so this lets the person see at once whether it is wider than meant.
  - The token is checked with the search API, a call that is known to work with this permission (no user information).
  - When the integration sees no page, it doesn't wait for Enter: it looks again by itself six times, five seconds apart, because a page just connected can show up in the list late. If there is still none it asks whether to keep waiting, go on or stop. Going on checks the page link given next by looking that page up directly, not through the list.
- **Limits:** whether in an environment variable or the Keychain, the AI can read the token if it tries from a shell. That can't be stopped, and the real defense is the pages connected to the integration. The Keychain works on macOS only; other systems are pointed to the environment variable. Making the integration and connecting pages can't be done through Notion's API, so they are only guided. Whether `!` in Claude Code's input gives the terminal this command needs is not confirmed, so a separate terminal is suggested.
- **Turned down:**
  - **Taking the token with `getpass` and putting it in the Keychain from lantern.** The token would pass through lantern's memory and arguments. When the Keychain tool takes it, it doesn't; the check then comes after saving.
  - **Environment variable only.** An AI tool opened from somewhere other than a terminal may not get it, and the person has to edit a shell settings file.
  - **The AI relaying the token in `/l-init`.** It stays in the conversation record.
  - **Printing the values for the person to carry to `/l-init` when there is no `lantern.yaml`.** It was so at first, and someone who ran the command before `/l-init` lost the values while believing it was connected.
  - **This command making `lantern.yaml`.** `/l-init` takes the file's being there for a re-run and skips its questions, so defaults nobody chose stay, and hooks work in a project that isn't set up.
  - **Keeping the chosen values in `.lantern/` for `/l-init` to use.** It needs more rules on when stale values are used and deleted. With the order put right they aren't needed.
  - **OAuth.** A public integration needs a client secret, which can't be in open source, and a server for the login.
  - **Reading the environment variable before the Keychain.** It was the first order, so that the value of someone who set the variable on purpose wouldn't be hidden, but in practice an old `export` line hid the new token (see "What actually happened").
- **What actually happened, and why the order was changed:** at first the variable was read first, and the value that the `export` line in `~/.zshrc` had put there when the terminal opened hid the token newly put in the Keychain, so the wizard got a 401. So the **Keychain is read first**. What the setup command manages is the Keychain, so it is always current, and someone with an old `export` line left doesn't have to change anything. The only thing lost is overriding the Keychain with a variable: different tokens per project are told apart by the name in `knowledge.token_env` (the Keychain item takes that name too), and where there is no Keychain or it is locked (not a Mac, a locked SSH session) the variable is used as it was. When the two differ it only says so, the token just typed is read from the Keychain for the check, and a 401 is shown as a short explanation instead of Notion's raw JSON answer.
- **Source:** `src/lanternspec/learn/knowledge/notion_setup.py` (the steps), `src/lanternspec/learn/knowledge/keychain.py` (the Keychain), `src/lanternspec/learn/knowledge/notion.py` (`notion_token`)

### Closed folders of the knowledge store (`knowledge.allow` · `knowledge.deny` · `lantern guard`)
- **Decided:** the folders of the knowledge store to open or to close are written in one place, `lantern.yaml`. lantern's search · read · write leave closed folders alone, and `lantern guard -- <tool>` starts the AI tool inside the operating system's sandbox so the tool can't open them directly either. Once any folder is closed, the store's hidden folders (`.git` and the like) are closed with it, and `lantern.yaml` can't be changed during a guarded run.
- **Why:**
  - Stopping lantern's own tools is not enough. An AI tool opens the store's folders directly with its file tools and by running commands.
  - The whole process is held instead of trusting the AI tool's settings. In a test, file tools · commands · scripts · subagents · a newly started session were all stopped, and the rules could not be loosened from inside.
  - What a closed folder holds also sits in copies: the history in `.git`, index files. Unless hidden folders are closed too, closed notes can still be read.
  - `lantern.yaml` is a file the AI tool can edit. Unless it is locked, the tool could take a folder off the list and open it on the next run.
  - A listed folder that is not in the store stops the run. A misspelled name would otherwise leave that folder open without anyone noticing.
  - Each operating system's own sandbox is used. On macOS `sandbox-exec` refuses to open the closed parts; on Linux bubblewrap (`bwrap`) lays an empty folder nobody can open over each closed folder and a read-only copy over `lantern.yaml`. The sandbox is tried once before the start, and when it can't start the tool isn't started either and the reason is shown.
  - The options a tool needs are decided by that tool's adapter file (`guarded_command`). Codex attaches to a shared server already running elsewhere and runs its commands there, so it is started without that server, and on macOS its own sandbox, on by default, is turned off. Claude Code · Antigravity start as typed.
- **Limits:** an AI tool started without the guarded run, and going through other programs that are already running (a session in another terminal, a local service), are not stopped. Material that must never leave belongs somewhere the AI tool's account can't read.
- **Turned down:**
  - **Leaving it to the AI tool's permission settings and its own sandbox.** Claude Code's sandbox holds only the commands it runs; its file tools are stopped by separate permission rules. Every tool has its own format, and some can only be set on a settings screen.
  - **Using it together with the AI tool's own sandbox.** macOS can't put a sandbox inside another, so on macOS the tool's own sandbox has to be off during a guarded run (Linux can nest them). For a tool whose sandbox is on by default, like Codex, lantern turns it off when starting it.
- **Source:** `src/lanternspec/learn/knowledge/access.py` (which folders are open), `src/lanternspec/tools/guard.py` (the guarded run)

### Components are kept as names in the session line, and only MCP tool calls are counted (`components`)
- **Decided:** when a conversation starts, the AI tool's settings files are read and the names of its MCP servers, plugins, skills you added and hook events go into the session line of the run log (`Tool.components`). `lantern eval` joins that list with the tool calls counted per turn and shows, per component, the sessions it was in and how often its MCP tools were called, and what was added or dropped between sessions (`report/components.py`).
- **Why:**
  - Connected is not the same as used. In an experiment comparing MCP servers, the connected MCP was never called and only the score table came out, so nobody noticed for a while. "Connected but 0 calls" is the cheapest and most reliable signal.
  - A setup changes without anyone noticing. In the same experiment the AI tool was upgraded, two built-in plugins appeared and the isolation check stopped every run. With a list kept per session you can tell when it changed.
  - Only names are kept. Commands, addresses and variables can carry tokens, and names are enough to compare.
  - It only reads. Starting the servers to check would slow down every conversation start. When a file can't be read, that part is left out and the rest goes on, which keeps the promise that an agent hook never stops the agent.
  - Only MCP tool calls are counted. The tool's name carries its server's name, so the call can be tied to it. For a skill that is not a lantern skill the log doesn't say which one was called, and a hook is not a tool call. They are not counted and the cell is left empty, so that 0 and unknown are not mixed.
  - Failures are counted apart. If only the calls that worked were counted, a server that is connected but unusable would look like calls = 0, the same as one that was never used. Failures come from `PostToolUseFailure`, which only fires for a tool that ran and failed (not for a call the person refused or cancelled). It fires rarely, so it is left out of the "silent hook" check.
  - The contract stays small. How to read the settings and how an AI tool names its tools differ per tool, so `Tool` gets two methods with defaults (`components` · `call_component`); only Claude Code implements them.
- **Limits:**
  - The docs don't say where user-scope MCP servers sit in `~/.claude.json`, so a top-level `mcpServers` is read when there is one. The local scope (`projects.<path>.mcpServers`) and the project scope (`.mcp.json`) are read as the docs say.
  - Plugins built into the tool and MCP servers deployed by an administrator are not read.
  - Everyday work mixes difficulty, model and date, so the numbers before and after a change can't be said to come from the setup. For now only the list and the call counts are shown.
- **Turned down:**
  - **Finding the connection state with `claude mcp list`.** It starts the servers, so every conversation start gets slower, and it doesn't fit the promise that an agent hook never stops the agent.
  - **Recommending which components to drop.** lantern doesn't rank what the user installed. What lantern builds itself is only what takes LanternSpec's documents as its source (see "What we build and what we leave to other tools" above), so it shows the facts only.
  - **Counting skill calls too.** The tool-call log doesn't say which skill, and adding it would count the total twice. It is added separately if the need shows up.
- **Source:** `src/lanternspec/tools/claude.py` (`components` · `call_component`), `src/lanternspec/tools/agent_hooks.py` (the session line), `src/lanternspec/report/components.py`

### A component card is a new template next to the decision records, and the bar is written when it is added (`lantern scaffold component`)
- **Decided:** when an MCP server, plugin, skill or hook is added, one page (`CMP-001 …`) holds why it was added, the expected effect, what to measure, the cost and the review time. It sits in the decisions folder, and its status is watching · keep · dropped. When a conversation starts and there is an MCP server or plugin that wasn't there before, the AI asks the user once whether to leave a card (`tools/components.py`).
- **Why:**
  - To say an effect, the bar has to exist first. The experiment comparing MCP servers had a hypothesis and a scoring bar, so it could say "it didn't improve", but everyday work has none. Written when the component is added, the numbers can't be fitted afterwards.
  - It is a new template. The status of a decision record (proposed · accepted · superseded) differs from this card's life (watching · keep · dropped), and adding parts to the decision record would add them to every ordinary decision too. The shape is the decision record's, so both are read together in one folder.
  - What to measure is picked from a list. Only what code can collect (calls · time · tokens · check errors · retro lines · review findings) counts as quantitative, so it can be collected automatically later.
  - Only MCP servers and plugins are asked about. Skills and hook events come and go in a person's own setup, and suggesting a card for each would be noise.
  - The first conversation only takes stock of what is there. Otherwise everything a person already has would be asked about the moment this is turned on. Once told, a component is not asked about again, whether or not a card was made (`.lantern/components-seen.json`).
  - Without a card the flow runs. It is an add-on, and the core flow doesn't go through it.
- **Turned down:**
  - **Adding parts to the decision record (ADR).** For the reason above.
  - **A new skill.** More skills blur the core flow, and a command and a template are enough. It is made if the need shows up.
  - **Letting people write the measure freely.** An item code can't collect can't be compared later.
  - **Asking about everything that looks new.** Narrowed to MCP servers and plugins for the reason above.
- **Limits:** only Claude Code is noticed (other tools have an empty list). If the settings can't be read in the first conversation, what was already there can look new later and be asked about once.
- **Source:** `src/lanternspec/tools/components.py` (noticing), `src/lanternspec/work/scaffold.py` (`new_component_card`), `resources/locales/<language>/templates/Component Card.md`

## 5. Changing this document
- A change to a rule or the flow updates that section's **decided · why · turned down** along with it.
- A new rule gets a new section. The rule's content goes in its rules document template; here, only the reasons and a link.
- If a test exposed the problem that led to the change, say what it exposed in a line or two under "why". Don't write planning document numbers.
