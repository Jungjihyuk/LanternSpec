---
name: l-idea
description: Turn a thought from the conversation into an idea note — record what the user said, word for word, plus a tidy version (one-line summary · why it helps · related documents) in docs/<<folder.ideas>>/IDEA-NNN right away. Overlapping ideas are added to the existing card. Use to capture an idea, feature wish, bug, experiment or tech review the user mentions ("it would be nice if…").
invocation: profile:idea.capture
argument-hint: "<a thought in one line> | the ideas from the conversation just now"
---

# /l-idea — turn a thought from the conversation into an idea note

**Purpose:** record a thought right away, **word for word plus a tidy version**. Speed matters, so **write it without asking for approval** (an exception to "show before writing").

Input: `$ARGUMENTS` — a thought in one line, or "the ideas from the conversation just now" (gather every idea from this conversation).

## Steps
1. **Pull out:** take the ideas out of what was said. Different thoughts become separate cards. Keep the original words unchanged.
2. **Check for overlap:** for each idea
   ```bash
   lantern idea find "<two or three key words>"
   ```
   - If the same idea exists, **don't create a new one.** Add to that card's `## <<section.raw>>` with the date (as a `> …` quote), and add only what is new to the tidy version.
   - If the same idea is <<idea_status.dropped.label>>, give the earlier reason (`dropped_reason`) and ask "bring it back?". If so, `lantern idea status IDEA-NNN "<<idea_status.new>>" --note "came up again"`.
3. **Pick the kind** (`idea_kind` in `docs/<<folder.templates>>/_meta/enums.yaml`): ✨ Feature · 🔧 Improvement · 🐞 Bug · 🧪 Experiment · 🔍 Tech Review. Bugs are gathered here too (task candidates in one place).
4. **Create · fill:**
   ```bash
   lantern scaffold idea "<short title>" --kind Feature --raw "<the user's words>"
   ```
   Fill only the blanks of the created file: one-line summary<<marker.required>> · why it helps · related documents (links only — never copy content). If you don't know, `<<marker.unknown>>`. Delete optional sections with nothing to write.
5. **Report in one line:** `💡 IDEA-014 Sign in with Google (Feature) recorded` (one line per card)

## The skills change the status
<<idea_status.new.label>> (`/l-idea`) → <<idea_status.reviewing.label>> · <<idea_status.worked.label>> (`/l-plan`) / <<idea_status.on_hold.label>> · <<idea_status.dropped.label>> (the person). When the person says <<idea_status.on_hold>> or <<idea_status.dropped>>:
```bash
lantern idea status IDEA-014 "<<idea_status.on_hold>>"
lantern idea status IDEA-014 "<<idea_status.dropped>>" --reason "<one-line reason <<marker.required>>>"
```
Dropped ideas are never deleted.

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
