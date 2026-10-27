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
    if name in REGISTRY:
        return REGISTRY[name]
    hint = f" → {RENAMED[name]}" if name in RENAMED else ""
    raise ValueError(f"지원하지 않는 도구: {name}{hint} (가능: {', '.join(NAMES)})")


def resolve(names: list[str]) -> list[Tool]:
    return [get(n) for n in names]


def config_paths() -> tuple[str, ...]:
    """Files · folders that belong to LanternSpec or an AI tool, not to the project's code."""
    return COMMON_PATHS + tuple(p for t in REGISTRY.values() for p in t.config_paths)


def is_config_path(rel: str) -> bool:
    return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in config_paths())
