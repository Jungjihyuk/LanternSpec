"""What every AI tool adapter provides — the contract the rest of LanternSpec talks to (C-05 · C-09).

A tool adapter answers three questions only, each in that tool's own format:
  1. skills  — where a skill goes and what its frontmatter looks like
  2. config  — which settings files carry our rules, hooks and MCP server
  3. hooks   — how its hook payload reads (parse_hook) and how an answer is written back (respond)

What a hook *does* (H-4 … H-10) lives in agent_hooks.py and never looks at a tool's format.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..core.project import Project, read, write

if TYPE_CHECKING:
    from ..core.enums import Enums
    from ..core.profile import Profile
    from .skills import SkillSource

GENERATED_NOTE = (
    "<!-- lanternspec가 생성한 파일 — 원본: lanternspec/resources/skills. "
    "`lantern upgrade`가 다시 만든다 (직접 고치면 upgrade가 건너뜀) -->\n"
)
HOOK_COMMAND = "if command -v lantern >/dev/null 2>&1; then lantern hook {event}{agent}; fi"
MCP_NAME = "lantern-knowledge"
MCP_SERVER = {"command": "lantern", "args": ["mcp"]}


@dataclass
class HookInput:
    """One hook call, in LanternSpec's words (each tool maps its own payload onto this)."""

    session: str = ""
    model: str = ""
    source: str = ""  # session-start: startup | resume | compact
    prompt: str = ""
    tool: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    cwd: str = ""
    turn_start: bool = True  # prompt: the first model call of a user turn
    finished: bool = True  # stop: the turn ended normally (not an error or a cancel)


@dataclass
class HookResult:
    """What a hook wants to say — each tool decides how to deliver it."""

    context: str = ""  # add to the model's context (H-4 · H-5 notes · H-9 · H-10)
    block: str = ""  # H-5: the doc just written is broken — fix it now
    notice: str = ""  # H-7: a one-line suggestion when the turn ends


@dataclass
class HookReply:
    stdout: str = ""
    stderr: str = ""
    code: int = 0


class Tool:
    name = ""
    label = ""
    launch = ""  # the terminal command that opens this tool (claude · codex · agy)
    skill_root = ""  # folder that holds <skill>/SKILL.md
    command_prefix = "/"  # how a user calls a skill: /l-build · $l-build
    session_expr = "$(date +%Y-%m-%d)"  # shell expression a skill passes as --session
    expands_arguments = False  # does the tool substitute $ARGUMENTS in a skill body?
    config_paths: tuple[str, ...] = ()  # files · folders this tool owns (not project code)
    write_tools: frozenset[str] = frozenset()  # tool names that write files (H-5)

    # ---- skills
    def skill_meta(self, src: SkillSource, profile: Profile, prefix: str) -> dict[str, Any]:
        from .skills import rewrite_commands

        return {"name": src.name, "description": rewrite_commands(src.description, prefix)}

    def skill_extras(self, src: SkillSource, profile: Profile) -> dict[str, str]:
        """Tool-only files next to SKILL.md (relative to the skill folder)."""
        return {}

    def skill_files(self, src: SkillSource, profile: Profile, prefix: str, enums: Enums | None = None) -> dict[str, str]:
        from .skills import render_body, rewrite_commands

        base = f"{self.skill_root}/{src.name}"
        body = render_body(src, profile, self, prefix, enums)
        files = {f"{base}/SKILL.md": yaml_front(self.skill_meta(src, profile, prefix)) + GENERATED_NOTE + "\n" + body}
        for rel, text in src.extra.items():
            files[f"{base}/{rel}"] = rewrite_commands(text, prefix)
        for rel, text in self.skill_extras(src, profile).items():
            files[f"{base}/{rel}"] = text
        return files

    def owns_skill_file(self, rel: str) -> bool:
        return rel.startswith(self.skill_root + "/")

    # ---- project config (rules · hooks · MCP); returns what was merged, for the install report
    def install_config(self, project: Project, mcp: bool) -> list[str]:
        return []

    # ---- hooks
    def hook_command(self, event: str) -> str:
        return HOOK_COMMAND.format(event=event, agent=f" --agent {self.name}")

    def parse_hook(self, event: str, data: dict[str, Any]) -> HookInput:
        raise NotImplementedError

    def written_paths(self, inp: HookInput) -> list[str]:
        return []

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
        raise NotImplementedError


# --------------------------------------------------------------------------- helpers for adapters


def yaml_front(meta: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=10_000) + "---\n"


def merge_json_file(path: Path, merge: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    data = json.loads(read(path)) if path.exists() and read(path).strip() else {}
    write(path, json.dumps(merge(data), ensure_ascii=False, indent=2) + "\n")


def is_our_hook(entry: dict[str, Any]) -> bool:
    cmds = [entry.get("command", "")] + [h.get("command", "") for h in entry.get("hooks", [])]
    return any("lantern hook" in c for c in cmds)


def replace_hook_entries(data: dict[str, Any], ours: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Claude-style `hooks: {Event: [entries]}` — drop our old entries, keep the user's, add ours."""
    hooks = data.setdefault("hooks", {})
    for event, entries in ours.items():
        hooks[event] = [e for e in hooks.get(event, []) if not is_our_hook(e)] + entries
    return data


def hook_state_dir(project: Project) -> Path:
    p = project.state / "hook-state"
    p.mkdir(parents=True, exist_ok=True)
    return p
