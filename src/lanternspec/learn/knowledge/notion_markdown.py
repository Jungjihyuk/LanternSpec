"""Turn a note's Markdown into Notion blocks: the same draft that reads well in Obsidian, in Notion's own forms.

Responsibilities:
    - blocks: headings, paragraphs, (nested) lists, checkboxes, quotes, Obsidian callouts, code, tables, formulas, dividers, images
    - text inside a line: bold, italic, strikethrough, highlight, code, links, formulas; what Notion has no form for becomes plain text
    - keep to what one request of the API takes (sizes, nesting)

Not here:
    - sending the blocks, reading them back → learn/knowledge/notion.py
    - the values of a row's properties → learn/knowledge/notion_database.py

Notes for Obsidian and Markdown folders never pass through here: they are stored as they were written.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

Block = dict[str, Any]

TEXT_CHARS = 1000  # Notion takes 2000 per piece of text, but counts an emoji as two
ARRAY = 100  # most items of any array (pieces of text, children of a block, blocks of a request)
REQUEST_BLOCKS = 1000  # most blocks of one request, the ones inside others included
REQUEST_BYTES = 400_000  # Notion takes 500 KB
CODE_PIECES = 50  # a longer code block is split, so that one block never fills a request
NESTING = 2  # how many levels of blocks inside a block one request takes
FORMULA_CHARS = 1000
URL_CHARS = 2000

# Obsidian's callout kinds and their other names → icon, color
_CALLOUTS = {
    ("abstract", "summary", "tldr"): ("📋", "blue_background"),
    ("note",): ("✏️", "blue_background"),
    ("info",): ("ℹ️", "blue_background"),
    ("todo",): ("☑️", "blue_background"),
    ("tip", "hint", "important"): ("💡", "green_background"),
    ("success", "check", "done"): ("✅", "green_background"),
    ("question", "help", "faq"): ("❓", "yellow_background"),
    ("warning", "caution", "attention"): ("⚠️", "orange_background"),
    ("failure", "fail", "missing"): ("❌", "red_background"),
    ("danger", "error"): ("⚡", "red_background"),
    ("bug",): ("🐞", "red_background"),
    ("example",): ("📑", "purple_background"),
    ("quote", "cite"): ("💬", "gray_background"),
}
CALLOUTS = {name: look for names, look in _CALLOUTS.items() for name in names}
OTHER_CALLOUT = ("📌", "gray_background")

# what Notion's code blocks can be (as its API answers to a wrong one), and the other names Markdown uses for them
LANGUAGES = frozenset(
    "abc agda arduino assembly bash basic bnf c c# c++ clojure coffeescript coq css dart dhall diff docker ebnf elixir elm erlang f# flow "
    "fortran gherkin glsl go graphql groovy haskell hcl html idris java javascript json julia kotlin latex less lisp livescript lua "
    "makefile markdown markup matlab mathematica mermaid nix objective-c ocaml pascal perl php powershell prolog protobuf purescript "
    "python r racket reason ruby rust sass scala scheme scss shell smalltalk solidity sql swift toml typescript vb.net verilog vhdl "
    "webassembly xml yaml".split()
)
ALIASES = {
    "rs": "rust", "py": "python", "python3": "python", "js": "javascript", "mjs": "javascript", "jsx": "javascript",
    "ts": "typescript", "tsx": "typescript", "sh": "shell", "zsh": "shell", "console": "shell", "shell-session": "shell",
    "yml": "yaml", "dockerfile": "docker", "cpp": "c++", "cc": "c++", "h": "c", "hpp": "c++", "cs": "c#", "csharp": "c#",
    "fs": "f#", "fsharp": "f#", "golang": "go", "kt": "kotlin", "kts": "kotlin", "rb": "ruby", "md": "markdown",
    "jsonc": "json", "json5": "json", "jsonl": "json", "make": "makefile", "ps1": "powershell", "proto": "protobuf",
    "tex": "latex", "math": "latex", "wasm": "webassembly", "wat": "webassembly", "objc": "objective-c", "hs": "haskell",
    "ex": "elixir", "erl": "erlang", "pl": "perl", "vb": "vb.net", "vue": "html", "svelte": "html", "svg": "xml", "patch": "diff",
    "gql": "graphql", "tf": "hcl", "terraform": "hcl", "asm": "assembly", "sol": "solidity",
    "postgresql": "sql", "mysql": "sql", "sqlite": "sql",
}  # fmt: skip


# --------------------------------------------------------------------------- text inside a line


@dataclass(frozen=True)
class _Piece:
    """A piece of text and how it looks."""

    text: str
    marks: frozenset[str] = frozenset()  # bold · italic · strikethrough · code · highlight · formula
    url: str = ""


_STASHED = re.compile("\x00(\\d+)\x00")
_LINK_TEXT = r"((?:[^\[\]]|\[[^\[\]]*\])*)"
_LINK_URL = r"<?((?:[^\s()<>]|\([^\s()]*\))+)>?(?:\s+[\"'][^)]*[\"'])?"
_STASH = re.compile(
    r"(?P<ticks>(?<!`)`+(?!`))(?P<code>.+?)(?<!`)(?P=ticks)(?!`)"
    r"|\\(?P<escaped>[!-/:-@\[-`{-~])"
    r"|(?P<hidden>%%.*?%%|<!--.*?-->)"
    r"|(?<!\$)\$(?=[^\s$])(?P<formula>[^$\n]*?)(?<=[^\s\\])\$(?![\d$])"
    rf"|!\[{_LINK_TEXT}\]\({_LINK_URL}\)"
    r"|!?\[\[(?P<wiki>[^\[\]\n]+)\]\]"
    r"|<(?P<auto>https?://[^>\s]+)>",
    re.S,
)
_LINK = re.compile(rf"(?<!!)\[{_LINK_TEXT}\]\({_LINK_URL}\)")
_BARE = re.compile(r"(?<![\w/])https?://[!#-'(-;=?-_a-z{}~]+")  # ASCII only: what follows an address in Korean is not part of it
_MARKS: list[tuple[re.Pattern[str], frozenset[str]]] = [
    (re.compile(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*(?!\*)", re.S), frozenset({"bold", "italic"})),
    (re.compile(r"\*\*(?=[^\s*])(.+?)(?<=\S)\*\*(?!\*)", re.S), frozenset({"bold"})),
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\*)", re.S), frozenset({"bold"})),
    (re.compile(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)", re.S), frozenset({"bold"})),
    (re.compile(r"(?<!\*)\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?!\*)", re.S), frozenset({"italic"})),
    (re.compile(r"(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)", re.S), frozenset({"italic"})),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S), frozenset({"strikethrough"})),
    (re.compile(r"==(?=[^\s=])(.+?)(?<=[^\s=])==", re.S), frozenset({"highlight"})),
]


def _usable(url: str) -> bool:
    """Whether Notion takes it as a link (it refuses addresses inside a vault or a repository)."""
    try:
        parts = urlparse(url)
    except ValueError:  # not an address after all, e.g. http://[a
        return False
    return len(url) <= URL_CHARS and (parts.scheme in ("http", "https") and bool(parts.netloc) or parts.scheme == "mailto")


def _wiki_text(inner: str) -> str:
    target, _, alias = inner.partition("|")
    return (alias or target.replace("#", " › ").removeprefix(" › ")).strip()


def _trim_address(url: str) -> str:
    url = url.rstrip(".,;:!?'*_~")
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1].rstrip(".,;:!?'*_~")
    return url


def _pieces(text: str) -> list[_Piece]:
    """Read a line's Markdown. Code, formulas and names are set aside first, so marks inside them stay as they are."""
    stash: list[_Piece] = []

    def keep(piece: _Piece) -> str:
        stash.append(piece)
        return f"\x00{len(stash) - 1}\x00"

    def set_aside(m: re.Match[str]) -> str:
        if m["code"] is not None:
            code = m["code"].replace("\n", " ")
            spaced = len(code) > 2 and code[0] == code[-1] == " " and bool(code.strip())
            return keep(_Piece(code[1:-1] if spaced else code, frozenset({"code"})))
        if m["escaped"]:
            return keep(_Piece(m["escaped"]))
        if m["hidden"]:
            return ""
        if m["formula"] is not None:
            return keep(_Piece(m["formula"], frozenset({"formula"})))
        if m["wiki"]:
            return keep(_Piece(_wiki_text(m["wiki"])))
        if m["auto"]:
            return keep(_Piece(m["auto"], url=m["auto"] if _usable(m["auto"]) else ""))
        alt, url = m[5], m[6]  # an image inside a line: its description, as a link
        return keep(_Piece(alt or url, url=url if _usable(url) else ""))

    text = _STASH.sub(set_aside, text.replace("\x00", ""))
    text = re.sub(r"<br\s*/?>", "\n", text)
    return _merge(_styled(text, _Piece(""), stash))


def _styled(text: str, look: _Piece, stash: list[_Piece]) -> Iterator[_Piece]:
    """Read links and marks from the left; what is set aside comes back with the look around it."""
    patterns = list(_MARKS)
    while text:
        found: list[tuple[int, int, str, _Piece]] = []  # start, end, inner text, its look
        if not look.url and (m := _LINK.search(text)):
            url = _STASHED.sub(lambda s: stash[int(s[1])].text, m[2])
            found.append((m.start(), m.end(), m[1], replace(look, url=url) if _usable(url) else look))
        if not look.url and (m := _BARE.search(text)) and _usable(url := _trim_address(m[0])):
            found.append((m.start(), m.start() + len(url), "", replace(look, text=url, url=url)))
        for pattern, marks in list(patterns):
            if m := pattern.search(text):
                found.append((m.start(), m.end(), m[1], replace(look, marks=look.marks | marks)))
            else:
                patterns.remove((pattern, marks))  # not in the rest of the text either
        if not found:
            break
        start, end, inner, inside = min(found, key=lambda f: f[0])  # the first one; among equals, the one tried first
        yield from _restored(text[:start], look, stash)
        if inside.text:
            yield inside
        else:
            yield from _styled(inner, inside, stash)
        text = text[end:]
    yield from _restored(text, look, stash)


def _restored(text: str, look: _Piece, stash: list[_Piece]) -> Iterator[_Piece]:
    """Text without marks, with what was set aside put back."""
    pos = 0
    for m in _STASHED.finditer(text):
        yield replace(look, text=text[pos : m.start()])
        kept = stash[int(m[1])]
        yield _Piece(kept.text, kept.marks | look.marks, look.url or kept.url)
        pos = m.end()
    yield replace(look, text=text[pos:])


def _merge(pieces: Iterator[_Piece]) -> list[_Piece]:
    """Drop empty pieces and join neighbors that look the same."""
    out: list[_Piece] = []
    for p in pieces:
        if not p.text:
            continue
        if out and (out[-1].marks, out[-1].url) == (p.marks, p.url) and "formula" not in p.marks:
            out[-1] = replace(out[-1], text=out[-1].text + p.text)
        else:
            out.append(p)
    return out


def _cut(text: str) -> list[str]:
    return [text[i : i + TEXT_CHARS] for i in range(0, len(text), TEXT_CHARS)]


def _objects(p: _Piece) -> list[dict[str, Any]]:
    """A piece as Notion's text objects."""
    if "formula" in p.marks and len(p.text) <= FORMULA_CHARS:
        return [{"type": "equation", "equation": {"expression": p.text}}]
    look: dict[str, Any] = {m: True for m in ("bold", "italic", "strikethrough", "code") if m in p.marks}
    if "highlight" in p.marks:
        look["color"] = "yellow_background"
    text = f"${p.text}$" if "formula" in p.marks else p.text
    out = []
    for part in _cut(text):
        item: dict[str, Any] = {"type": "text", "text": {"content": part}}
        if p.url:
            item["text"]["link"] = {"url": p.url}
        if look:
            item["annotations"] = look
        out.append(item)
    return out


def rich_text(text: str, bold: bool = False) -> list[dict[str, Any]]:
    """Turn the Markdown of one line into Notion's text objects.

    Args:
        text: The text, with its marks.
        bold: Make all of it bold.

    Returns:
        The text objects; what is past Notion's limit of them is kept without its looks.

    Example:
        >>> [(t["text"]["content"], t.get("annotations")) for t in rich_text("**Ser**de는 `x`")]
        [('Ser', {'bold': True}), ('de는 ', None), ('x', {'code': True})]
    """
    pieces = [replace(p, marks=p.marks | {"bold"}) if bold else p for p in _pieces(text)]
    out: list[dict[str, Any]] = []
    for i, p in enumerate(pieces):
        made = _objects(p)
        rest = _cut("".join(x.text for x in pieces[i:]))
        if len(out) + len(made) + len(_cut("".join(x.text for x in pieces[i + 1 :]))) > ARRAY:
            return out + [{"type": "text", "text": {"content": part}} for part in rest]
        out += made
    return out


# --------------------------------------------------------------------------- blocks

_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`]*)$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_DIVIDER = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(\s+)(\S.*)$")
_QUOTE = re.compile(r"^ {0,3}> ?")
_CALLOUT = re.compile(r"^\s*\[!([\w-]+)(?:\|[^\]]*)?\][+-]?\s*(.*)$")
_TASK = re.compile(r"^\[(.)\]\s+(.*)$", re.S)
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
_IMAGE = re.compile(rf"^\s*!\[{_LINK_TEXT}\]\({_LINK_URL}\)\s*$")
_IMAGE_FILE = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|bmp|tiff?|heic)(?:\?.*)?$", re.I)
_UNDERLINE = re.compile(r"^ {0,3}(=+|-{2,})\s*$")


def _block(kind: str, **body: Any) -> Block:
    return {"object": "block", "type": kind, kind: body}


def _with(block: Block, children: list[Block]) -> Block:
    if children:
        block[block["type"]]["children"] = children
    return block


def _indent(line: str) -> int:
    line = line.expandtabs(4)
    return len(line) - len(line.lstrip(" "))


def _dedent(line: str, width: int) -> str:
    """Take up to `width` columns of indentation off a line."""
    if not line.startswith((" ", "\t")):
        return line
    body = line.lstrip(" \t")
    head = line[: len(line) - len(body)].expandtabs(4)
    return head[width:] + body


def _cells(line: str) -> list[str]:
    inner = line.strip().removeprefix("|")
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", inner)]


def _is_table(lines: list[str], i: int) -> bool:
    if i + 1 >= len(lines) or "|" not in lines[i] or "-" not in lines[i + 1] or not _TABLE_RULE.match(lines[i + 1]):
        return False
    return len(_cells(lines[i])) == len(_cells(lines[i + 1]))


def _starts_block(lines: list[str], i: int) -> bool:
    """Whether a line ends the paragraph before it (a number other than 1 is more likely part of the sentence)."""
    line = lines[i]
    item = _ITEM.match(line)
    return bool(
        not line.strip()
        or _FENCE.match(line)
        or _HEADING.match(line)
        or _DIVIDER.match(line)
        or _QUOTE.match(line)
        or line.strip().startswith(("$$", "<!--", "%%"))
        or (item and (not item[2][0].isdigit() or int(item[2][:-1]) == 1))
        or _IMAGE.match(line)
        or _is_table(lines, i)
    )


def _language(info: str) -> str:
    word = re.split(r"[\s,:{]", info.strip().lstrip("{."))[0].strip("}").lower()
    word = ALIASES.get(word, word)
    return word if word in LANGUAGES else "plain text"


def _code(text: str, language: str) -> list[Block]:
    """Code as one block, or as several when it is very long."""
    parts = [{"type": "text", "text": {"content": p}} for p in _cut(text)]
    return [_block("code", rich_text=parts[i : i + CODE_PIECES], language=language) for i in range(0, max(len(parts), 1), CODE_PIECES)]


def _take_fence(lines: list[str], i: int) -> tuple[list[Block], int]:
    m = _FENCE.match(lines[i])
    assert m
    mark, body = m[2], []
    width = _indent(lines[i])
    i += 1
    while i < len(lines) and not re.match(rf"^\s*{re.escape(mark[0])}{{{len(mark)},}}\s*$", lines[i]):
        body.append(_dedent(lines[i], width))
        i += 1
    return _code("\n".join(body), _language(m[3])), i + 1


def _take_formula(lines: list[str], i: int) -> tuple[list[Block], int]:
    text = lines[i].strip()[2:]
    i += 1
    while "$$" not in text and i < len(lines):
        text += "\n" + lines[i]
        i += 1
    expression, _, after = text.partition("$$")
    expression = expression.strip()
    if not expression or len(expression) > FORMULA_CHARS:
        made = _code(expression, "latex") if expression else []
    else:
        made = [_block("equation", expression=expression)]
    return made + (_paragraph([after]) if after.strip() else []), i


def _take_hidden(lines: list[str], i: int) -> tuple[list[str], int]:
    """Skip a comment (`%%` or `<!--`), giving back what follows it on its last line."""
    text = lines[i].strip()
    end = "-->" if text.startswith("<!--") else "%%"
    text = text[4 if end == "-->" else 2 :]
    i += 1
    while end not in text and i < len(lines):
        text = lines[i]
        i += 1
    after = text.partition(end)[2]
    return ([after] if after.strip() else []), i


def _take_quote(lines: list[str], i: int) -> tuple[list[Block], int]:
    inner = []
    while i < len(lines) and _QUOTE.match(lines[i]):
        inner.append(_QUOTE.sub("", lines[i], count=1))
        i += 1
    callout = _CALLOUT.match(inner[0])
    if callout:
        icon, color = CALLOUTS.get(callout[1].lower(), OTHER_CALLOUT)
        title, children = rich_text(callout[2], bold=True), _parse(inner[1:])
        if not title:
            title, children = _lead(children)
        look = {"icon": {"type": "emoji", "emoji": icon}, "color": color}
        return [_with(_block("callout", rich_text=title, **look), children)], i
    title, children = _lead(_parse(inner))
    return [_with(_block("quote", rich_text=title), children)] if title or children else [], i


def _lead(blocks: list[Block]) -> tuple[list[dict[str, Any]], list[Block]]:
    """The text of a first paragraph, to stand in the block itself, and the blocks that go inside it."""
    if blocks and blocks[0]["type"] in ("paragraph", "heading_1", "heading_2", "heading_3", "heading_4"):
        first = blocks[0][blocks[0]["type"]]
        return first["rich_text"], first.get("children", []) + blocks[1:]
    return [], blocks


def _take_table(lines: list[str], i: int) -> tuple[list[Block], int]:
    rows = [_cells(lines[i])]
    i += 2
    while i < len(lines) and lines[i].strip() and "|" in lines[i]:
        rows.append(_cells(lines[i]))
        i += 1
    width = max(len(r) for r in rows)
    made = [_block("table_row", cells=[rich_text(c) for c in r + [""] * (width - len(r))]) for r in rows]
    head, body = made[0], made[1:]
    step = ARRAY - 1  # a longer table goes on in another one with the same header
    return [
        _block("table", table_width=width, has_column_header=True, has_row_header=False, children=[head, *body[k : k + step]])
        for k in range(0, max(len(body), 1), step)
    ], i


def _take_item(lines: list[str], i: int, restart: bool) -> tuple[list[Block], int]:
    """One list item with everything indented under it."""
    m = _ITEM.match(lines[i])
    assert m
    own = _indent(lines[i])
    width = own + len(m[2]) + min(len(m[3]), 4)
    inner = [m[4]]
    fence = ""
    i += 1
    if f := _FENCE.match(m[4]):
        fence = f[2]
    while i < len(lines):
        line = lines[i]
        if not fence and not line.strip():  # a blank line belongs here when what follows it is indented under the item
            after = next((x for x in lines[i:] if x.strip()), "")
            if not after or _indent(after) <= own:
                break
        elif not fence and _indent(line) <= own:
            if not inner[-1].strip() or _starts_block(lines, i) or _ITEM.match(line):
                break  # not a line of the same paragraph
        if f := _FENCE.match(line):
            if not fence:
                fence = f[2]
            elif f[2][0] == fence[0] and len(f[2]) >= len(fence) and not f[3].strip():
                fence = ""
        inner.append(_dedent(line, width))
        i += 1
    task = _TASK.match(m[4]) if not m[2][0].isdigit() else None
    if task:
        inner[0] = task[2]
    text, children = _lead(_parse(inner))
    if task:
        block = _block("to_do", rich_text=text, checked=task[1] in "xX")
    elif not m[2][0].isdigit():
        block = _block("bulleted_list_item", rich_text=text)
    elif restart:  # Notion would count from 1 here, so the number stays as text
        block = _block("paragraph", rich_text=[{"type": "text", "text": {"content": m[2] + " "}}, *text][:ARRAY])
    else:
        block = _block("numbered_list_item", rich_text=text)
    return [_with(block, children)], i


def _paragraph(lines: list[str]) -> list[Block]:
    text = "\n".join(re.sub(r"\\$", "", line.strip()) for line in lines)
    made = rich_text(text)
    return [_block("paragraph", rich_text=made)] if made else []


def _parse(lines: list[str]) -> list[Block]:
    """Read lines as blocks."""
    out: list[Block] = []
    lines = list(lines)
    i = 0
    numbered = False  # the block before was an item of a numbered list that Notion counts by itself
    while i < len(lines):
        line = lines[i]
        item = _ITEM.match(line)
        if not line.strip():
            i += 1
            continue
        was_numbered, numbered = numbered, False
        if _FENCE.match(line):
            made, i = _take_fence(lines, i)
        elif line.strip().startswith("$$"):
            made, i = _take_formula(lines, i)
        elif line.strip().startswith(("<!--", "%%")):
            rest, i = _take_hidden(lines, i)
            lines[i:i] = rest
            made, numbered = [], was_numbered
        elif m := _HEADING.match(line):
            made, i = [_block(f"heading_{min(len(m[1]), 4)}", rich_text=rich_text(m[2]))], i + 1
        elif _DIVIDER.match(line):
            made, i = [_block("divider")], i + 1
        elif _QUOTE.match(line):
            made, i = _take_quote(lines, i)
        elif item:
            number = int(item[2][:-1]) if item[2][0].isdigit() else 0
            restart = number > 1 and not was_numbered
            made, i = _take_item(lines, i, restart)
            numbered = number > 0 and not restart
        elif _is_table(lines, i):
            made, i = _take_table(lines, i)
        elif (m := _IMAGE.match(line)) and _usable(m[2]) and _IMAGE_FILE.search(m[2]):
            made, i = [_block("image", type="external", external={"url": m[2]}, caption=rich_text(m[1]))], i + 1
        else:
            start = i
            i += 1
            while i < len(lines) and not _starts_block(lines, i) and not _UNDERLINE.match(lines[i]):
                i += 1
            if i < len(lines) and (m := _UNDERLINE.match(lines[i])):
                text = " ".join(x.strip() for x in lines[start:i])
                made, i = [_block("heading_1" if m[1][0] == "=" else "heading_2", rich_text=rich_text(text))], i + 1
            else:
                made = _paragraph(lines[start:i])
        out += made
    return out


def _plain(block: Block) -> str:
    return "".join(
        t["text"]["content"] if t["type"] == "text" else t["equation"]["expression"] for t in block[block["type"]].get("rich_text") or []
    )


def _table_text(block: Block) -> list[Block]:
    """A table as text, for a place too deep to hold one."""
    rows = [
        " | ".join(_plain({"type": "cell", "cell": {"rich_text": c}}) for c in r["table_row"]["cells"]) for r in block["table"]["children"]
    ]
    return _code("\n".join(rows), "plain text")


def _fit(blocks: list[Block], depth: int = 0) -> list[Block]:
    """Keep to the nesting and the number of children one request takes: what doesn't fit comes right after, nothing is dropped."""
    out: list[Block] = []
    for block in blocks:
        body = block[block["type"]]
        children = body.pop("children", [])
        if block["type"] == "table":
            if depth >= NESTING:
                out += _table_text({"type": "table", "table": {"children": children}})
                continue
            body["children"] = children
            out.append(block)
        elif depth >= NESTING:
            out += [block, *_fit(children, depth)]
        else:
            inside = _fit(children, depth + 1)
            out.append(_with(block, inside[:ARRAY]))
            out += inside[ARRAY:]
    return out


def markdown_to_blocks(md: str) -> list[Block]:
    r"""Turn Markdown, with what Obsidian adds to it, into Notion blocks.

    Links inside a vault have no place in Notion and become text. Comments are left out, as Obsidian hides them.

    Args:
        md: Markdown text, without frontmatter.

    Returns:
        Notion blocks, each small enough for one request.

    Example:
        >>> [b["type"] for b in markdown_to_blocks("# 제목\n- 하나\n> 인용\n\n본문\n1. 첫째")]
        ['heading_1', 'bulleted_list_item', 'quote', 'paragraph', 'numbered_list_item']
        >>> markdown_to_blocks("> [!tip] 요령\n> 본문")[0]["callout"]["icon"]["emoji"]
        '💡'
    """
    return _fit(_parse(md.replace("\r\n", "\n").split("\n")))


def without_title(blocks: list[Block], title: str) -> list[Block]:
    """Leave out a first heading that only repeats the page's title, which Notion shows above the text.

    Args:
        blocks: The note's blocks.
        title: The page's title.

    Returns:
        The blocks to send.

    Example:
        >>> without_title(markdown_to_blocks("# Serde"), "serde")
        []
    """
    repeats = blocks and blocks[0]["type"] == "heading_1" and _plain(blocks[0]).strip().casefold() == title.strip().casefold()
    return blocks[1:] if repeats else blocks


def _count(block: Block) -> int:
    return 1 + sum(_count(c) for c in block[block["type"]].get("children") or [])


def requests(blocks: list[Block]) -> list[list[Block]]:
    r"""Divide blocks into what one request takes.

    Args:
        blocks: The blocks, in order.

    Returns:
        Groups of blocks, in order; one empty group when there are none.

    Example:
        >>> [len(g) for g in requests(markdown_to_blocks("- a\n" * 250))]
        [100, 100, 50]
    """
    groups: list[list[Block]] = [[]]
    count = size = 0
    for block in blocks:
        n, length = _count(block), len(json.dumps(block))
        if groups[-1] and (len(groups[-1]) >= ARRAY or count + n > REQUEST_BLOCKS or size + length > REQUEST_BYTES):
            groups.append([])
            count = size = 0
        groups[-1].append(block)
        count, size = count + n, size + length
    return groups
