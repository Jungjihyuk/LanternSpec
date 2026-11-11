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

### Design approval
- **Decided:** a person approves the design before building.
- **Why:** AI writes a lot of code quickly in the wrong direction too. Stopping at the design is far cheaper than turning around after the code is written.

## 2. Where documents live

### Why `2. Work` and `3. Current State` are separate
- **Decided:** work documents (plan · design · tasks · log) live in the work's folder; what the program is like now lives in `3. Current State`, which changes only when a work finishes, after approval.
- **Why:** work documents say "what we meant to do then"; the current state says "how it is now". Kept together, ongoing plans and the real state mix, and the AI reads features not yet built as existing.

### Finished works go to the archive
- **Why:** so only works in progress stand out, while the record of finished ones is kept, not deleted.
- **With parallel works:** a work another running work links to is archived later, so its paths don't change while another worktree reads its documents.

### The rules folder (`3. Current State/Rules/`)
- **Decided:** the rules a project follows (development principles · tech selection criteria · repository file rules · task breakdown rules …) live as documents in the rules folder, and skills read and follow them.
- **Why:** a rule kept only inside a skill's text is hard for people to find and impossible for a team to change. As a document, a rule the team changed is followed by the AI too.
- **Turned down:** writing the rules into skills. Skills are regenerated on `lantern upgrade`, and the team's edits would be lost.

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
- **Decided:** the time axis holds **only real times**: when work was actually done, and dates a person planned. Only stretches with work get fine columns (5 minutes to an hour); an hour or more without any task is folded and labelled like "⋯ 5 h ⋯". A finished task shows how long it took as text. Tasks not started and without a date wait in a "no date yet" column on the right with their size; dragging one onto a day plans it.
- **Why:**
  - AI work comes in bursts with long gaps. Drawn by days, minute-long tasks pile into one column; drawn by hours, most of the chart is empty.
  - A size says how much work, not when. Putting undated tasks on the axis with a length guessed from their size needed a conversion like "hours in a day", and that guess even changed the column size.
- **Turned down:** estimated bars chaining unstarted tasks by order and size. They ignored nights and weekends, looking like overnight work, and on a day chart `1h` filled a whole day. For a forecast, `lantern task estimate` suggests dates and skips weekends.
- **Source:** `src/lanternspec/resources/obsidian/lantern-timeline/main.js`

### Kanban
- **Decided:** works appear as cards in stage columns (plan · design · tasks · build · done), and clicking a card opens that work's tasks in a window. It is read only.
- **Why:**
  - The timeline answers "what was done when", the kanban "where is each work held up now". They answer different questions, so both stay instead of making people pick one.
  - Stage columns are more useful than three columns (not started · in progress · done). LanternSpec works pass stages by waiting for a person's check, so the column where cards pile up shows what is held back.
  - Cards aren't dragged to change a stage. Skills move stages through checks like design approval, and `/l-build` checks tasks off as it leaves tests and evidence; changing them on screen would skip those checks.
- **Turned down:** adding a kanban view to the Lantern Timeline plugin. The timeline and the kanban change for different reasons, so one plugin would mean touching one to change the other. As two plugins, a view nobody wants can be turned off in Obsidian's settings.
- **Source:** `src/lanternspec/resources/obsidian/lantern-kanban/`; the data comes from `report/views.py`

## 5. Changing this document
- A change to a rule or the flow updates that section's **decided · why · turned down** along with it.
- A new rule gets a new section. The rule's content goes in its rules document template; here, only the reasons and a link.
- If a test exposed the problem that led to the change, say what it exposed in a line or two under "why". Don't write planning document numbers.
