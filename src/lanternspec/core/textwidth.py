"""How many columns a text takes in a terminal (Korean and other wide letters take two).

Responsibilities:
    - count the columns of a text
    - cut a text to a number of columns

Not here:
    - drawing tables with it → cli/table.py
"""

from __future__ import annotations

import unicodedata


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


def cut(text: str, width: int) -> str:
    """Cut a text to at most `width` columns, ending in "…" when something was left out.

    Args:
        text: The text.
        width: The most columns the result may take (including the "…").

    Returns:
        The text itself when it fits.

    Example:
        >>> cut("abcdef", 4), cut("한글입니다", 7), cut("한글", 7)
        ('abc…', '한글입…', '한글')
    """
    if cells(text) <= width:
        return text
    out, used = "", 0
    for c in text:
        w = cells(c)
        if used + w > width - 1:
            break
        out, used = out + c, used + w
    return out + "…"
