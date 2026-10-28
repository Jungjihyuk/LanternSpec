"""AI-tool connection — install skills, rules and agent hooks in each tool's format, and handle the hooks.

When one tool's format changes, only that tool's file changes (claude.py · codex.py · antigravity.py).
A new tool needs one file implementing base.Tool and one line in REGISTRY below.
"""

from __future__ import annotations

from .antigravity import Antigravity
from .base import Tool
from .claude import ClaudeCode
from .codex import Codex

REGISTRY: dict[str, Tool] = {t.name: t for t in (ClaudeCode(), Codex(), Antigravity())}
NAMES = list(REGISTRY)
RENAMED = {"gemini": "antigravity (Gemini CLI는 Antigravity CLI로 바뀌었습니다)"}
COMMON_PATHS = ("lantern.yaml", "AGENTS.md", ".lantern/")


def get(name: str) -> Tool:
    """Return a supported AI tool by name.

    Args:
        name: Tool name, e.g. "claude".

    Returns:
        The tool adapter.

    Raises:
        ValueError: The tool is not supported (renamed tools say what replaced them).

    Example:
        >>> get("codex").label
        'Codex'
    """
    if name in REGISTRY:
        return REGISTRY[name]
    hint = f" → {RENAMED[name]}" if name in RENAMED else ""
    raise ValueError(f"지원하지 않는 도구: {name}{hint} (가능: {', '.join(NAMES)})")


def resolve(names: list[str]) -> list[Tool]:
    """Return the tool adapters for several names.

    Args:
        names: Tool names.

    Returns:
        The adapters, in the same order.

    Raises:
        ValueError: One of the tools is not supported.

    Example:
        >>> [t.name for t in resolve(["claude", "codex"])]
        ['claude', 'codex']
    """
    return [get(n) for n in names]


def config_paths() -> tuple[str, ...]:
    """List the files and folders that belong to LanternSpec or an AI tool, not to the project's code.

    Returns:
        Paths relative to the project root; folders end with "/".

    Example:
        >>> "AGENTS.md" in config_paths()
        True
    """
    return COMMON_PATHS + tuple(p for t in REGISTRY.values() for p in t.config_paths)


def is_config_path(rel: str) -> bool:
    """Tell whether a path belongs to LanternSpec or an AI tool (see config_paths).

    Args:
        rel: Path relative to the project root.

    Returns:
        True for tool settings, False for project code.

    Example:
        >>> is_config_path(".lantern/runs.jsonl"), is_config_path("src/app.py")
        (True, False)
    """
    return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in config_paths())
