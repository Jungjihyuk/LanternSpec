# /l-ref domain — say what each section is about and when to read it

Domain knowledge is read **only when needed**, one section at a time. The AI finds its way through one index (`lantern ref domain`) — propose four things per section, and the person approves.
Documents put in `<<folder.domain>>/` need no listing. Other paths are listed at step 3 (index).

| What to set | How |
|---|---|
| What `--what` | The section's **topic only**. Never its rule (numbers · deadlines · conditions) — so nobody acts on the index alone |
| When to read `--when` | The situation that calls for it (e.g. "writing code that stores or deletes member data"). This is what sends the AI there |
| Key terms `--keys` | Two or three words that lead to it |
| Verbatim `--verbatim` | Sections with numbers · deadlines · exceptions; their exact words are read again right before deciding. Propose it by default when they have them |

## 0. Convert the originals (before step 3's index)
Large, numerous material costs a lot of tokens. **Never read originals (PDF · HWP · Excel …) directly, and never read copies whole.**
```bash
lantern ref convert [path]            # shows what is there, sizes and duplicates (writes nothing)
lantern ref convert [path] --apply    # writes the copies (the originals stay)
```
- Show the list first and let the person choose the scope: everything / one folder / a few. Split it up when there is a lot.
- Pass on the quality marks as they are. ⚠ means headings or tables were partly lost, so numbers should be checked against the original; ✖ means no text (a scan), so the person puts in an OCR'd `.md`. Report failed files with their hint and move on.
- A data file's copy (XLSX · CSV) is a card of sheets, columns and row counts. The values stay in the original, for code to read.

## 1. Propose
- Handle only the `+` · `~` sections from step 3's output. **Propose from `lantern ref preview "<document>"`** — it shows each section's address, line count and first lines.
- Open a section with `lantern ref read "<address>"` only when the preview doesn't tell what it is (outside material too). Don't read the sections one after another.
- For a copy cut into pages or parts, pages on one topic can be proposed as one line.
- For a data card, write only what and when; never copy its values into the index.
- One line per section: `address — what — when to read — key terms — verbatim or not`.
- When the sub-sections are short, describe the section above them instead (its sub-sections are read with it). Leave out front matter · contents · revision history, shown as "sections to leave out".

## 2. Store what was approved
```bash
lantern ref describe "<address>" --what "topic" --when "situation" [--keys "word, word"] [--verbatim]
lantern ref describe "<address>" --off        # take the description away
lantern ref exclude "<address>"               # leave a section out of this project
lantern ref domain                            # show the index
```
- Inside material also shows in `<<folder.domain>>/<<file.domain_moc>>` (generated — don't edit it). Descriptions of outside material stay only in this computer's `.lantern/`.
- A ⚠ in the index means the section changed after it was described — read it again and fix the description.
- Reading is `/l-domain`'s and `lantern ref read`'s job; tying sections to a work is `/l-plan`'s.
