"""How big a rules file may be, from the limits of the installed AI tools — measured in bytes and lines, never tokens.

Every tokenizer spends at least one byte per token, so a text of N bytes is at most N tokens for any
model. Comparing bytes with a token limit is therefore safe whatever the model, needs no tokenizer
or API, and always gives the same answer for the same file. Korean (3 bytes a letter) and English
(1 byte) weigh differently on their own.

Responsibilities:
    - the budget of the root AGENTS.md and of a folder's AGENTS.md, from the installed tools' limits
    - measure a rules file and say which part (LanternSpec's block or the person's text) is large

Not here:
    - each tool's limits → the tool files (Tool.rules_max_lines · rules_max_bytes · rules_chain_max_bytes · hook_context_max_tokens)
    - showing the result → check/doctor.py · tools/install.py
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..core.messages import msg

MARGIN = 0.9  # stay this far inside the tightest limit


@dataclass
class Budget:
    """How big one rules file may be; None where no installed tool sets a limit.

    Attributes:
        max_lines: Lines.
        max_bytes: Bytes (UTF-8).

    Example:
        >>> Budget(200, None).max_lines
        200
    """

    max_lines: int | None
    max_bytes: int | None


def _tightest(values: Iterable[int]) -> int | None:
    found = [v for v in values if v > 0]
    return min(found) if found else None


def root_budget(tools: Iterable[object]) -> Budget:
    """The budget of the root AGENTS.md, which every tool reads at the start of a session.

    Args:
        tools: The installed tool adapters.

    Returns:
        The tightest line limit as is (a guideline), and the tightest byte limit with a margin.

    Example:
        >>> from lanternspec.tools import resolve
        >>> root_budget(resolve(["claude", "antigravity"]))
        Budget(max_lines=200, max_bytes=21600)
    """
    tools = list(tools)
    lines = _tightest(getattr(t, "rules_max_lines", 0) for t in tools)
    raw = _tightest([*(getattr(t, "rules_max_bytes", 0) for t in tools), *(getattr(t, "rules_chain_max_bytes", 0) for t in tools)])
    return Budget(lines, int(raw * MARGIN) if raw else None)


def folder_budget(tools: Iterable[object]) -> Budget:
    """The budget of a folder's AGENTS.md, which a hook may have to hand to the AI in one go.

    A hook's token limit counts as that many bytes (one token is at least one byte).

    Args:
        tools: The installed tool adapters.

    Returns:
        The budget, with a margin on bytes.

    Example:
        >>> from lanternspec.tools import resolve
        >>> folder_budget(resolve(["claude", "codex"]))
        Budget(max_lines=200, max_bytes=7200)
    """
    tools = list(tools)
    lines = _tightest(getattr(t, "rules_max_lines", 0) for t in tools)
    raw = _tightest([*(getattr(t, "rules_max_bytes", 0) for t in tools), *(getattr(t, "hook_context_max_tokens", 0) for t in tools)])
    return Budget(lines, int(raw * MARGIN) if raw else None)


def size(text: str) -> tuple[int, int]:
    r"""Measure a text.

    Args:
        text: The text.

    Returns:
        (UTF-8 bytes, lines).

    Example:
        >>> size("가나\nab\n")
        (10, 2)
    """
    return len(text.encode("utf-8")), len(text.splitlines())


def parts(text: str, start: str, end: str) -> tuple[int, int]:
    r"""Split a rules file's bytes into LanternSpec's block and the person's own text.

    Args:
        text: The rules file.
        start: The mark opening LanternSpec's block.
        end: The mark closing it.

    Returns:
        (bytes of the block, bytes of everything else).

    Example:
        >>> parts("# 우리\n<!-- s -->\nab\n<!-- e -->\n", "<!-- s -->", "<!-- e -->")
        (24, 10)
    """
    s, e = text.find(start), text.find(end)
    if s == -1 or e < s:
        return 0, size(text)[0]
    block = text[s : e + len(end)]
    return size(block)[0], size(text)[0] - size(block)[0]


def check(name: str, text: str, budget: Budget, start: str, end: str) -> tuple[str, str]:
    r"""Compare a rules file with its budget.

    Args:
        name: How to call the file, e.g. "AGENTS.md".
        text: Its text.
        budget: Its budget.
        start: The mark opening LanternSpec's block.
        end: The mark closing it.

    Returns:
        ("ok" | "warn", message); over budget says which part is large.

    Example:
        >>> check("AGENTS.md", "a\n" * 300, Budget(200, None), "<s>", "<e>")[0]
        'warn'
    """
    n_bytes, n_lines = size(text)
    over_lines = budget.max_lines is not None and n_lines > budget.max_lines
    over_bytes = budget.max_bytes is not None and n_bytes > budget.max_bytes
    limits = [f"{budget.max_bytes / 1024:.1f}KB"] if budget.max_bytes else []
    limits += [msg("{count} lines", count=budget.max_lines)] if budget.max_lines else []
    now = msg(
        "{name} {kb:.1f}KB · {lines} lines (budget {budget})", name=name, kb=n_bytes / 1024, lines=n_lines, budget=" · ".join(limits) or "-"
    )
    if not (over_lines or over_bytes):
        return "ok", now
    block, own = parts(text, start, end)
    return "warn", now + msg(
        " — over budget: LanternSpec's block {block:.1f}KB · your own text {own:.1f}KB; move details into documents and link them",
        block=block / 1024,
        own=own / 1024,
    )
