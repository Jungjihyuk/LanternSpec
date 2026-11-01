# /l-ref terms — choose the company terms

Company glossaries come in every shape, so **the original stays as it is** and only the approved terms go into the index.
They are shown merged with the project glossary (`<<folder.rules>>/<<file.glossary>>`) by `lantern ref terms`; when a term is in both, the company's wins.

## 1. Propose
- Read the `+` · `~` sections of step 3's output with `lantern ref read "<address>"` (outside material too).
- One line per term: `term — one-line meaning — words to avoid — scope`.
  - **Words to avoid**: only those the original says not to use ("don't say …", "instead of …"). If it says none, leave it empty — never guess.
  - Scope: `all` (empty = all) · a part's folder · a language.
- With many terms, show first those that appear in this project's documents and code — leave the rest to "read with `lantern ref read` when needed".
- Point out terms already in the project glossary with another meaning (the company's wins).

## 2. Store what was approved
```bash
lantern ref term <glossary document> "<term>" --avoid "word, word" --meaning "one line" [--scope <scope>]
lantern ref term <glossary document> "<term>" --off      # take the approval away
lantern ref terms                                         # see the merged table
```
- The document name is the one in the index output (without `.md`). A term the original doesn't mention isn't stored.
- `lantern check` finds the words to avoid in documents (`docs/` only, outside code blocks and inline code).
