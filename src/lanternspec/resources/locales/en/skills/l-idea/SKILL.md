---
name: l-idea
description: Keep a thought for later — an idea, a wish, an annoyance, something that looks like a bug, a technology to look into or an experiment to try that would be forgotten if not written down, recorded word for word plus a tidy version in docs/<<folder.ideas>>/IDEA-NNN. Offer it even when it doesn't fit a kind (feature · improvement · bug · experiment · tech review) exactly. Overlapping cards get it added. Use when the conversation shows a thought worth keeping for later — a wish, an annoyance, a possible bug, a technology to look into, an experiment to try ("it would be nice if…", "this is a bit of a hassle", "looks like a bug, let's look later").
invocation: profile:idea.capture
argument-hint: "<a thought in one line> | the ideas from the conversation just now"
---

# /l-idea — turn a thought from the conversation into an idea note

**Purpose:** record a thought right away, **word for word plus a tidy version**. Speed matters, so **write it without asking for approval** (an exception to "show before writing").

Input: `$ARGUMENTS` — a thought in one line, or "the ideas from the conversation just now" (gather every idea from this conversation).

## When to offer it
When the conversation shows **a thought worth bringing back later**, ask in one line, after the person has finished, whether to keep it. For example: "Shall I keep this as an idea? (`/l-idea`)"
- These are the signs:
  - a wish ("it would be nice if…", "someday I'd like to…")
  - an annoyance ("… is a hassle", "every time I have to…")
  - odd behavior ("… shows up wrong", "sometimes … happens")
  - a technology to look into ("what about …?", "I'd like to try …")
  - an experiment ("would … make it faster?")
- **Offer it even when it doesn't fit a kind exactly.** Pick the nearest kind when recording; if unsure, ask.
- Don't offer it for work just decided to be done now — that belongs to `/l-plan` or the current work.
- Don't offer the same thought twice in one conversation. If the person says not to keep it, don't ask again in that conversation.

## Steps
1. **Pull out:** take the ideas out of what was said. Different thoughts become separate cards. Keep the original words unchanged.
2. **Check for overlap:** for each idea
   ```bash
   lantern idea find "<two or three key words>"
   ```
   - If the same idea exists, **don't create a new one.** Add to that card's `## <<section.raw>>` with the date (as a `> …` quote), and add only what is new to the tidy version.
   - If the same idea is <<idea_status.dropped.label>>, give the earlier reason (`dropped_reason`) and ask "bring it back?". If so, `lantern idea status IDEA-NNN "<<idea_status.new>>" --note "came up again"`.
   - If the same idea is <<idea_status.blocked.label>>, give why it is blocked and what would reopen it, and ask whether that has happened.
3. **Pick the kind** (`idea_kind` in `docs/<<folder.templates>>/_meta/enums.yaml`): ✨ Feature · 🔧 Improvement · 🐞 Bug · 🧪 Experiment · 🔍 Tech Review. Bugs are gathered here too (task candidates in one place).
4. **Create · fill:**
   ```bash
   lantern scaffold idea "<short title>" --kind Feature --raw "<the user's words>"
   ```
   If the kind has its own template (`docs/<<folder.templates>>/<<doc.idea>> - <kind>.md`, e.g. Feature → a feature summary table) the card is made from it, otherwise from the plain `<<doc.idea>>` template.
   Fill only the blanks of the created file: one-line summary<<marker.required>> · that template's sections · related documents (links only — never copy content). Delete optional sections with nothing to write.
   Fill table cells only as far as the conversation went; leave unknown cells empty rather than guessing. Don't touch the tables filled in afterwards (result · cause and fix · conclusion) — `/l-build` fills them when it wraps up. In a written section, if you don't know, `<<marker.unknown>>`.
5. **Report in one line:** `💡 IDEA-014 Sign in with Google (Feature) recorded` (one line per card)

## The skills change the status
<<idea_status.new.label>> (`/l-idea`) → <<idea_status.reviewing.label>> · <<idea_status.worked.label>> (`/l-plan`) / <<idea_status.on_hold.label>> · <<idea_status.dropped.label>> (the person). When the person says <<idea_status.on_hold>> or <<idea_status.dropped>>:
```bash
lantern idea status IDEA-014 "<<idea_status.on_hold>>"
lantern idea status IDEA-014 "<<idea_status.dropped>>" --reason "<one-line reason <<marker.required>>>"
```
Dropped ideas are never deleted.

## Blocked ideas
What is wanted but not possible now (a technical limit · skill · experience · missing data) is <<idea_status.blocked>>, not <<idea_status.on_hold>>. <<idea_status.on_hold>> is simply put off; <<idea_status.blocked>> says what would reopen it.
```bash
lantern idea status IDEA-014 "<<idea_status.blocked>>" --reason "<what blocks it · what was tried>" --revisit "<what would reopen it>"
lantern debt promote IDEA-014 "<what to learn>"   # only when a person's skill blocks it: makes a <<debt_kind.competency.label>> card, linked both ways
```
- Write `--revisit` so it can be checked. Bad: "when the tech gets better". Good: "when an HWP tool reads table structure".
- Both values come from what the person said; ask if you don't know. `<<file.moc>>` gathers the blocked list.

<!-- lantern:if idea.capture=ask -->
## Noticing during the conversation (idea.capture: ask)
When the user says something idea-like during the conversation ("it would be nice if…", "later we could also…") (the agent hook tells you with a `LanternSpec idea` message), finish what you were doing and then ask **in one line only**: "💡 Keep this as an idea?" — ask **only once per conversation**, and don't ask again if they say no.
<!-- lantern:endif -->
<!-- lantern:if idea.capture=auto -->
## Recording on its own (idea.capture: auto)
When the user says something idea-like during the conversation, record it without asking: `lantern scaffold idea "<title>" --kind <kind> --raw "<the words>" --auto` (it gets a `🤖 recorded automatically` mark). Don't stop what you were doing; report in one line: `💡🤖 IDEA-015 … recorded automatically (tell me if that's wrong)`.
<!-- lantern:endif -->

## Common wrap-up
```bash
lantern close l-idea
```

**Next:** if you decide to build it, `/l-plan IDEA-014`.
