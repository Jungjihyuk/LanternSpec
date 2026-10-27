"""AI 도구 연결 — 스킬 · 규칙 · 에이전트 hook을 각 도구 형식으로 설치하고, hook을 받아 처리한다.

도구 하나의 형식이 바뀌면 그 도구 파일(claude.py · codex.py · antigravity.py) 하나만 고친다.
새 도구는 base.Tool을 구현한 파일 하나와 아래 REGISTRY 한 줄이면 된다.
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
