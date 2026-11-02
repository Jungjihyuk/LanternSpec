"""Color the status marks (✔ ⚠ ✖ ℹ) of command output on a terminal.

Responsibilities:
    - pick a color for a line from the mark it starts with
    - wrap stdout · stderr so every print gets colored, only on a terminal and without NO_COLOR

Not here:
    - which mark a line gets → the command or the check that writes it
"""

from __future__ import annotations

import os
import sys
from typing import Any, TextIO

RESET = "\033[0m"
WHOLE_LINE = {"✖": "\033[31m", "⚠": "\033[33m"}  # problems and warnings: the whole line stands out
MARK_ONLY = {"✔": "\033[32m", "ℹ": "\033[36m"}  # fine and notes: only the mark, so the text stays calm


def paint(line: str) -> str:
    r"""Color one output line by the mark it starts with (after its indentation).

    Args:
        line: One line without its newline.

    Returns:
        The line with ANSI colors; unchanged when it starts with no mark.

    Example:
        >>> paint("⚠ hook이 실행되지 않았습니다")
        '\x1b[33m⚠ hook이 실행되지 않았습니다\x1b[0m'
        >>> paint("  ✔ 양식에 맞음")
        '  \x1b[32m✔\x1b[0m 양식에 맞음'
        >>> paint("📄 docs/기획.md")
        '📄 docs/기획.md'
    """
    text = line.lstrip(" ")
    pad = line[: len(line) - len(text)]
    mark = text[:1]
    if mark in WHOLE_LINE:
        return f"{pad}{WHOLE_LINE[mark]}{text}{RESET}"
    if mark in MARK_ONLY:
        return f"{pad}{MARK_ONLY[mark]}{mark}{RESET}{text[1:]}"
    return line


class _Painted:
    """A text stream that colors each complete line before passing it on."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.pending = ""

    def write(self, s: str) -> int:
        *done, self.pending = (self.pending + s).split("\n")
        for line in done:
            self.stream.write(paint(line) + "\n")
        return len(s)

    def flush(self) -> None:
        if self.pending:
            self.stream.write(paint(self.pending))
            self.pending = ""
        self.stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


def wanted(stream: TextIO) -> bool:
    """Say whether to color a stream: a terminal, NO_COLOR unset, and not a dumb terminal.

    Args:
        stream: The stream to write to.

    Returns:
        True when colors are wanted.

    Example:
        >>> import io
        >>> wanted(io.StringIO())
        False
    """
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def enable() -> None:
    """Wrap stdout and stderr so status marks are colored, where colors are wanted.

    Example:
        >>> enable()  # doctest: +SKIP
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if not isinstance(stream, _Painted) and wanted(stream):
            setattr(sys, name, _Painted(stream))
