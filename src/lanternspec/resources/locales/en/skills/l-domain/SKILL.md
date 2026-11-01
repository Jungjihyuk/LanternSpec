---
name: l-domain
description: Find and read domain knowledge — when something depends on domain knowledge brought into the project (law, policy, business rules), find the section that fits the situation in the index (lantern ref domain), read only that section in its own words, and follow it. Use when a question, a design choice or a change depends on domain rules the project may hold.
invocation: model
argument-hint: "[what you need to know]"
---

# /l-domain — find and read domain knowledge

**Purpose:** read only the section you need, right when you need it, and use it at once. Never put the whole index or a whole document into the context.

Input: `$ARGUMENTS` — what you need to know (empty: judge from the conversation).

## 1. Find
1. If a work is in progress, look first at what is tied to it: `lantern ref domain --work W-012 [--task T03]`. If a section fits, go to 2.
2. Otherwise look at the index: `lantern ref domain`. Pick the section whose **"When to read"** fits the situation.
   - "What" is only the topic — never answer from it. The rule itself is only in the original words.
   - If no section fits, don't make one up: say "the domain knowledge brought in doesn't cover this" and ask the person.

## 2. Read
```bash
lantern ref read "<address>"
```
- One section at a time. A long section lists its sub-sections; read only the one you need.
- **📌 Verbatim:** follow its numbers · deadlines · exceptions exactly as written. Read it again right before turning the decision into code or documents.
- **⚠ Changed since indexed:** follow the original words, and tell the person in one line to fix the index with `/l-ref domain`.
- Never open material outside the project with file tools. Never copy its path, titles or words into files that go into git (documents · code · commit messages).

## 3. Tie it
A section newly read inside a work gets tied to it — so after compaction, and for the next person, it is clear what the work relied on:
```bash
lantern ref attach "<address>" --work W-012 [--task T03] --note "what it was used for"
```

## Common wrap-up
```bash
lantern close l-domain
```
