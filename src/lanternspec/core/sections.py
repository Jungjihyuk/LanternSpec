r"""Find, read and change one `## ` section of a document, accepting any of its titles.

A protected section may have been renamed by the project, so callers pass every accepted title
(core/names.py `Names.titles`). When the section is missing, nothing is added: callers skip
the feature and `lantern check` asks the person what they meant.

Not here:
    - which titles a section may have → core/names.py
    - asking about missing sections → check/check_docs.py
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .messages import msg
from .names import Names

TEMPLATE_ONLY = "<!-- lantern:template-only -->"


class SectionMissing(LookupError):
    """A command needs a protected section that the document no longer has.

    The message says which section, what it is for, and what the person can do.

    Attributes:
        role: The section's role, e.g. "unit_log".
        path: The document.

    Example:
        >>> from lanternspec.core.names import load
        >>> str(SectionMissing(load("ko"), "known_list", Path("아는 기술.md"))).split(" — ")[0]
        "아는 기술.md에 '목록' 칸이 없어 기록하지 못했습니다"
    """

    def __init__(self, names: Names, role: str, path: Path) -> None:
        """Build the message.

        Args:
            names: The project's names.
            role: The section's role.
            path: The document.
        """
        self.role, self.path = role, path
        s = names.section(role)
        super().__init__(
            msg(
                "Couldn't record it: {name} has no '{title}' section — this section {feature}. "
                'If you renamed it, lantern sections rename {role} "new title"; if you don\'t use it, lantern sections off {role}',
                name=path.name,
                title=names.title(role),
                feature=s.feature,
                role=role,
            )
        )


def find(text: str, titles: Iterable[str]) -> re.Match[str] | None:
    r"""Find a `## title` line and its content, trying the titles in order.

    The content runs to the next `## ` heading or the template-only mark.

    Args:
        text: The whole document.
        titles: Accepted titles, most preferred first.

    Returns:
        A match whose group 1 is the heading line and group 2 the content; None when no title is found.

    Example:
        >>> m = find("## 오늘\nA\n## 다음\nB\n", ["지금 상황", "오늘"])
        >>> m.group(2)
        'A\n'
    """
    for title in titles:
        m = re.search(rf"^(## {re.escape(title)}[ \t]*\n)(.*?)(?=^## |^{re.escape(TEMPLATE_ONLY)}|\Z)", text, re.M | re.S)
        if m:
            return m
    return None


def has(text: str, titles: Iterable[str]) -> bool:
    r"""Tell whether a document has the section under any of its titles.

    Args:
        text: The whole document.
        titles: Accepted titles.

    Returns:
        True when one of the titles is a `## ` heading.

    Example:
        >>> has("## 원문\n…\n", ["원문"]), has("## 메모\n", ["원문"])
        (True, False)
    """
    return find(text, titles) is not None


def body(text: str, titles: Iterable[str]) -> str:
    r"""Return a section's content without `> [!guide]` lines.

    Args:
        text: The whole document.
        titles: Accepted titles.

    Returns:
        The content, stripped; "" when the section is missing.

    Example:
        >>> body("## 지금 상황\n> [!guide] 덮어쓴다\n- 진행: A\n", ["지금 상황"])
        '- 진행: A'
    """
    m = find(text, titles)
    if m is None:
        return ""
    return "\n".join(l for l in m.group(2).split("\n") if not l.startswith("> [!guide]")).strip()


def replace(text: str, titles: Iterable[str], content: str) -> tuple[str, str] | None:
    r"""Replace a section's content, keeping its guide lines.

    Args:
        text: The whole document.
        titles: Accepted titles.
        content: New content.

    Returns:
        (new document, previous content); None when the section is missing.

    Example:
        >>> new, old = replace("## 지금 상황\n> [!guide] 덮어쓴다\n- A\n## 증거\n", ["지금 상황"], "- B")
        >>> old
        '- A'
        >>> print(new, end="")
        ## 지금 상황
        > [!guide] 덮어쓴다
        <BLANKLINE>
        - B
        <BLANKLINE>
        ## 증거
    """
    titles = list(titles)
    m = find(text, titles)
    if m is None:
        return None
    guides = [l for l in m.group(2).split("\n") if l.startswith("> [!guide]")]
    old = body(text, titles)
    block = "\n".join(guides) + ("\n\n" if guides else "") + content.strip() + "\n\n"
    return text[: m.start(2)] + block + text[m.end(2) :], old


def append(text: str, titles: Iterable[str], line: str) -> str | None:
    r"""Add a line at the end of a section's content (before its trailing blank lines and any comment mark).

    Args:
        text: The whole document.
        titles: Accepted titles.
        line: The line (or lines) to add.

    Returns:
        The new document; None when the section is missing.

    Example:
        >>> print(append("## 상태 기록\n- 1일 새것\n\n## 끝\n", ["상태 기록"], "- 2일 검토"), end="")
        ## 상태 기록
        - 1일 새것
        - 2일 검토
        <BLANKLINE>
        ## 끝
    """
    m = find(text, titles)
    if m is None:
        return None
    parts = m.group(2).split("\n")
    insert_at = len(parts)
    for i, l in enumerate(parts):
        if l.startswith("<!--"):
            insert_at = i
            break
    while insert_at > 0 and parts[insert_at - 1].strip() == "":
        insert_at -= 1
    parts.insert(insert_at, line)
    return text[: m.start(2)] + "\n".join(parts) + text[m.end(2) :]
