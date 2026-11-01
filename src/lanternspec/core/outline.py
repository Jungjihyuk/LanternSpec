r"""Read a Markdown document as a tree of headings and cut out one section by its titles.

A section is one heading and everything below it up to the next heading of the same or a higher
level (sub-sections included) — the unit of Obsidian's `[[문서#제목]]`. Sections are addressed by
their titles, never by line numbers, which shift whenever the document is edited.

Responsibilities:
    - list the headings (outside the frontmatter and fenced code) and the sections they open
    - find a section by its title, or with the titles above it when the title repeats (`위#아래`)
    - hash a section so a change is noticed, ignoring changes that keep the meaning (trailing spaces · blank lines at the ends)
    - point out structure that makes sections hard to address (no headings · skipped levels · very long sections)

Not here:
    - the protected `## ` sections code reads and writes → core/sections.py
    - which documents are references and where their index lives → refs/
"""

from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from dataclasses import dataclass

from .messages import msg

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
LONG_SECTION = 200  # lines of a section's own text (without its sub-sections) worth splitting
SHORT_DOCUMENT = 40  # a document this short needs no headings


@dataclass(frozen=True)
class Section:
    """One heading and its text, sub-sections included.

    Attributes:
        titles: The titles from the top heading down to this one (a lone `# ` title above it is left out).
        level: The heading level (1 for `#`).
        start: The heading's line index.
        end: The index of the line after the section.
        own_end: The index where its first sub-section starts (end when it has none).

    Example:
        >>> Section(("개인정보", "보관 기간"), 2, 4, 9, 9).address
        '개인정보#보관 기간'
    """

    titles: tuple[str, ...]
    level: int
    start: int
    end: int
    own_end: int

    @property
    def title(self) -> str:
        """The section's own title."""
        return self.titles[-1]

    @property
    def address(self) -> str:
        """The titles joined with `#`, as in `[[문서#위#아래]]`."""
        return "#".join(self.titles)


def sections(text: str) -> list[Section]:
    r"""List the sections of a document in order.

    Lines in the frontmatter and in fenced code are not headings. A document whose first heading is its
    only `# ` heading wears that title as its name; it is left out of the addresses below it.

    Args:
        text: The whole document.

    Returns:
        One Section per heading.

    Example:
        >>> doc = "---\nid: a\n---\n# 법\n## 보관\n```\n# 코드\n```\n### 기한\n## 파기\n"
        >>> [(s.address, s.start, s.end) for s in sections(doc)]
        [('법', 3, 11), ('보관', 4, 9), ('보관#기한', 8, 9), ('파기', 9, 11)]
        >>> [s.address for s in sections("# 1장\n## 목적\n# 2장\n## 목적\n")]
        ['1장', '1장#목적', '2장', '2장#목적']
    """
    lines = text.split("\n")
    first = 0
    if lines and lines[0].strip() == "---":
        first = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    heads: list[tuple[int, int, str]] = []
    fence = ""
    for i in range(first, len(lines)):
        mark = FENCE.match(lines[i])
        if mark:
            fence = "" if fence == mark.group(1) else fence or mark.group(1)
            continue
        h = None if fence else HEADING.match(lines[i])
        if h:
            heads.append((i, len(h.group(1)), h.group(2).strip()))
    lone_top = bool(heads) and heads[0][1] == 1 and sum(lv == 1 for _, lv, _ in heads) == 1
    out = []
    stack: list[tuple[int, str]] = []
    for n, (i, level, title) in enumerate(heads):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        end = next((j for j, lv, _ in heads[n + 1 :] if lv <= level), len(lines))
        own_end = heads[n + 1][0] if n + 1 < len(heads) and heads[n + 1][0] < end else end
        titles = tuple(t for _, t in stack)
        out.append(Section(titles[1:] if lone_top and n else titles, level, i, end, own_end))
    return out


def _key(title: str) -> str:
    return " ".join(unicodedata.normalize("NFC", title).casefold().split())


def find(text: str, query: str) -> list[Section]:
    r"""Find the sections a title (or `위#아래` titles) points at.

    The last title must be the section's own; the titles before it must appear above it, in order,
    but may skip levels. Case and repeated spaces don't matter.

    Args:
        text: The whole document.
        query: "제목" or "위 제목#제목".

    Returns:
        Every matching section; more than one means the title repeats and needs a title above it.

    Example:
        >>> doc = "# 법\n## 회원\n### 보관\n## 주문\n### 보관\n"
        >>> [s.address for s in find(doc, "보관")]
        ['회원#보관', '주문#보관']
        >>> [s.address for s in find(doc, "주문#보관")]
        ['주문#보관']
    """
    want = [_key(t) for t in query.split("#") if t.strip()]
    if not want:
        return []
    out = []
    for s in sections(text):
        keys = [_key(t) for t in s.titles]
        if keys[-1] != want[-1]:
            continue
        above = iter(keys[:-1])
        if all(any(k == w for k in above) for w in want[:-1]):
            out.append(s)
    return out


def cut(text: str, section: Section) -> str:
    r"""Return the section's lines, sub-sections included.

    Args:
        text: The whole document.
        section: A section of that text.

    Returns:
        The heading line and its text, ending with one newline.

    Example:
        >>> doc = "# 법\n## 보관\n3년\n## 파기\n"
        >>> cut(doc, find(doc, "보관")[0])
        '## 보관\n3년\n'
    """
    return "\n".join(text.split("\n")[section.start : section.end]).rstrip() + "\n"


def digest(text: str) -> str:
    r"""Hash a text so only changes in meaning count.

    Trailing spaces, blank lines at the start and end, line endings and Unicode normalization are ignored.

    Args:
        text: A document or a section.

    Returns:
        16 hex characters.

    Example:
        >>> digest("## 보관\n3년  \n\n") == digest("\n## 보관\r\n3년\n")
        True
        >>> digest("## 보관\n3년\n") == digest("## 보관\n5년\n")
        False
    """
    lines = [line.rstrip() for line in unicodedata.normalize("NFC", text).replace("\r\n", "\n").split("\n")]
    return hashlib.sha256("\n".join(lines).strip("\n").encode("utf-8")).hexdigest()[:16]


def problems(text: str) -> list[str]:
    r"""Point out structure that keeps parts of a document from being read on their own.

    Args:
        text: The whole document.

    Returns:
        One message per problem: no headings in a long document, a skipped heading level, a very long section.

    Example:
        >>> problems("# 법\n### 보관\n")
        ["'보관': 제목 급을 건너뛰었습니다 (# → ###)"]
        >>> problems("# 법\n## 보관\n3년\n")
        []
    """
    found = sections(text)
    lines = text.split("\n")
    if not found:
        if len(lines) > SHORT_DOCUMENT:
            return [msg("No headings in {count} lines — add `##` headings so one part can be read alone", count=len(lines))]
        return []
    out = []
    for prev, s in zip([None, *found], found, strict=False):
        if prev is not None and s.level > prev.level + 1:
            out.append(msg("'{title}': a heading level is skipped ({a} → {b})", title=s.title, a="#" * prev.level, b="#" * s.level))
        if s.own_end - s.start > LONG_SECTION:
            out.append(
                msg(
                    "'{title}' runs {count} lines without a sub-heading — split it so it can be read in parts",
                    title=s.title,
                    count=s.own_end - s.start,
                )
            )
    return out


def similar(text: str, query: str, limit: int = 3) -> list[str]:
    r"""Suggest section addresses close to a title that wasn't found.

    Args:
        text: The whole document.
        query: The title (or `위#아래` titles) that wasn't found.
        limit: At most this many suggestions.

    Returns:
        Addresses, closest first.

    Example:
        >>> similar("# 법\n## 보관 기간\n## 파기\n", "보관기간")
        ['보관 기간']
    """
    found = sections(text)
    by_title: dict[str, list[str]] = {}
    for s in found:
        by_title.setdefault(_key(s.title), []).append(s.address)
    want = _key(query.split("#")[-1])
    close = difflib.get_close_matches(want, list(by_title), n=limit, cutoff=0.5)
    return [a for k in close for a in by_title[k]][:limit]
