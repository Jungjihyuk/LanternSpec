"""Draw the Markdown tables of a report as aligned columns for a terminal.

Responsibilities:
    - line the columns up by the columns a terminal uses (Korean and other wide letters take two)
    - drop the Markdown marks around a title (`**…**`) and a note (`_…_`) that a terminal shows as plain characters

Not here:
    - writing the tables → report/*.py (they stay Markdown, because the Obsidian reports use them)
    - coloring status marks → cli/color.py
"""

from __future__ import annotations

import re
import unicodedata
from typing import TextIO

_RULE = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+$")  # the line under a table's header: |---|---|
_NUMBER = re.compile(r"^(\d[\d.,]*%?|—)$")  # a cell that is a number (or the dash for "none"), so its column is right-aligned


def cells(text: str) -> int:
    r"""Count the columns a text takes in a terminal.

    Args:
        text: One line of text without ANSI colors.

    Returns:
        Two for each wide letter (Korean, Chinese, Japanese, full-width forms), none for a combining mark, one otherwise.

    Example:
        >>> cells("abc"), cells("한글"), cells("e\u0301")
        (3, 4, 1)
    """
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _split(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _draw(rows: list[list[str]]) -> list[str]:
    """Lay one table out: the header, a rule, the rows; a column of numbers is right-aligned."""
    count = len(rows[0])
    rows = [[*r, *[""] * (count - len(r))][:count] for r in rows]
    widths = [max(cells(r[i]) for r in rows) for i in range(count)]
    numeric = [any(r[i] != "—" for r in rows[1:]) and all(_NUMBER.match(r[i]) for r in rows[1:]) for i in range(count)]

    def line(row: list[str]) -> str:
        parts = [(" " * (widths[i] - cells(c)) + c) if numeric[i] else c + " " * (widths[i] - cells(c)) for i, c in enumerate(row)]
        return " │ ".join(parts).rstrip()

    rule = "─┼─".join("─" * w for w in widths)
    return [line(rows[0]), rule, *(line(r) for r in rows[1:])]


def render(markdown: str) -> str:
    r"""Turn the Markdown tables of a report into aligned columns and drop the marks around titles and notes.

    Args:
        markdown: The report text.

    Returns:
        The text for a terminal; a line that is not part of a table is kept as it is.

    Example:
        >>> print(render("| a | b |\n|---|---|\n| 가 | 12 |"))
        a  │  b
        ───┼───
        가 │ 12
    """
    lines = markdown.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("|") and lines[i].rstrip().endswith("|") and i + 1 < len(lines) and _RULE.match(lines[i + 1].strip()):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.extend(_draw([_split(lines[i]), *(_split(x) for x in lines[i + 2 : j])]))
            i = j
            continue
        line = lines[i]
        if re.fullmatch(r"\*\*[^*]+\*\*", line) or re.fullmatch(r"_[^_].*[^_]_", line):
            line = line[2:-2] if line.startswith("**") else line[1:-1]
        out.append(line)
        i += 1
    return "\n".join(out)


def for_terminal(markdown: str, stream: TextIO) -> str:
    r"""Pick how a report is printed: aligned columns on a terminal, the Markdown as it is for a file or a pipe.

    Args:
        markdown: The report text.
        stream: Where it is printed.

    Returns:
        The text to print.

    Example:
        >>> import io
        >>> for_terminal("| a |\n|---|\n| b |", io.StringIO())
        '| a |\n|---|\n| b |'
    """
    return render(markdown) if stream.isatty() else markdown
