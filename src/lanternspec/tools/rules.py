"""AGENTS.md — the one rules file every tool reads (Claude Code through CLAUDE.md's `@AGENTS.md`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import resources
from ..core import principles, templating
from ..core.profile import FOLDERS, Profile
from .skills import PROFILE_TOKEN, body_context, command_prefix, rewrite_commands

if TYPE_CHECKING:
    from ..core.enums import Enums
    from .base import Tool

AGENTS_START, AGENTS_END = "<!-- lanternspec:start -->", "<!-- lanternspec:end -->"
PRINCIPLES_SLOT = "<!-- lantern:principles -->"


def agents_block(profile: Profile, tools: list[Tool], enums: Enums | None = None) -> str:
    text = resources.read_text("agents/AGENTS.md")
    ctx = body_context(profile, "agents", enums)
    text = rewrite_commands(templating.apply_conditions(text, ctx), command_prefix(tools))
    text = PROFILE_TOKEN.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), text)
    section = principles_section(profile)
    text = text.replace(f"\n{PRINCIPLES_SLOT}\n", f"\n{section}\n" if section else "")
    return f"{AGENTS_START}\n{text.strip()}\n{AGENTS_END}"


def merge_block(existing: str, block: str) -> str:
    s, e = existing.find(AGENTS_START), existing.find(AGENTS_END)
    if s != -1 and e != -1 and e > s:
        return existing[:s] + block + existing[e + len(AGENTS_END) :]
    if existing.strip():
        return existing.rstrip() + "\n\n" + block + "\n"
    return "# AGENTS.md\n\n" + block + "\n"


def principles_section(profile: Profile) -> str:
    """AGENTS.md 블록에 넣을 개발 원칙 · 코드 컨벤션 — 핵심만 (자세한 설명은 개발 원칙 문서)."""
    sel = principles.select(profile)
    if sel is None:
        return ""
    names = principles.table()["levels"]
    doc = f"{profile.docs_root}/{FOLDERS['rules']}/개발 원칙.md"
    lines = [f"### 개발 원칙 — {sel.summary()}", f"자세히: `{doc}` (자동 생성 · `lantern principles show`)"]
    for level in ("must", "should"):
        chosen = sel.at(level)
        if chosen:
            lines.append(f"- **{names[level]}:** " + " · ".join(p.name for p in chosen))
    lines.append(f"- {principles.table()['priority']}")
    lines.append("- **작업 방식:** " + " · ".join(name for name, _ in sel.always))
    if sel.conventions:
        lines += ["", "### 코드 컨벤션 — " + " · ".join(c.label for c in sel.conventions)]
        cmds = [(principles.ROLE_LABEL[r], profile.get(f"build.{r}")) for r in (*principles.COMMAND_ROLES, "test")]
        cmds = [f"{label} `{cmd}`" for label, cmd in cmds if cmd]
        if cmds:
            lines.append("- 고친 뒤 돌리고 모두 통과해야 끝: " + " · ".join(cmds) + " — 린트 · 타입 검사는 `lantern lint`로 한 번에")
        language = principles.DOC_LANGUAGE.get(profile.comment_language, profile.comment_language)
        for c in sel.conventions:
            prefix = f"{c.label} " if len(sel.conventions) > 1 else ""
            lines.append(f"- {prefix}타입 힌트: {c.rules['type_hints']}")
            lines.append(f"- {prefix}문서 주석 ({c.docs_style} · {language}): {c.rules['docs']}")
    return "\n".join(lines)
