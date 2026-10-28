---
name: l-map
description: Refresh the document map (MOC) — rewrite the folder blocks of docs/<<file.moc>> (role · files · template · command, works by stage) from the current folders, templates and commands. What people wrote is outside the l-map marks and never overwritten. Use when folders or documents were added, moved or renamed.
invocation: model
---

# /l-map — refresh the document map

**Purpose:** rebuild the MOC to match the folders as they are now. The script does all of it.

```bash
lantern map
```

- Only the part between `<!-- l-map:start -->` and `<!-- l-map:end -->` is rewritten. Tell people to keep what they write **outside** it.
- If nothing changed, the file is left untouched.
- Report in one line: number of folders · works in progress · works waiting for approval.
- If links look broken, suggest `lantern check` next.

The other skills' common wrap-up (`lantern close`) already runs `map`, so you rarely need to call this directly.
