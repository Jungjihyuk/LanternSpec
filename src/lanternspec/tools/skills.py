"""One skill source (Agent Skills standard, resources/skills) → each tool's skill files (C-05).

Rendering is tool-agnostic: profile values and conditions are filled in here; a tool adapter
only says where the files go and what frontmatter they carry (tools/<tool>.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .. import resources
from ..core import enums as enums_mod
from ..core import frontmatter, templating
from ..core.profile import Profile

if TYPE_CHECKING:
    from .base import Tool

SKILL_NAMES = [
    "l-init",
    "l-idea",
    "l-plan",
    "l-design",
    "l-task",
    "l-build",
    "l-learn",
    "l-report",
    "l-template",
    "l-check",
    "l-sync",
    "l-map",
    "l-adr",
]
NAME_RE = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")
CMD_RE = re.compile(r"(?<![\w/$.-])/(" + "|".join(re.escape(n) for n in SKILL_NAMES) + r")\b")
SESSION_TOKEN = "<<SESSION_ID>>"
PROFILE_TOKEN = re.compile(r"<<([a-z_]+(?:\.[a-z_]+)+)>>")  # profile values and enum roles


@dataclass
class SkillSource:
    name: str
    description: str
    invocation: str  # model | manual | profile:<dotted key>
    argument_hint: str
    body: str
    extra: dict[str, str] = field(default_factory=dict)  # relative path -> text (references/…)

    def manual_only(self, profile: Profile) -> bool:
        if self.invocation == "manual":
            return True
        if self.invocation.startswith("profile:"):
            return str(profile.get(self.invocation.split(":", 1)[1])) == "manual"
        return False


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ValueError(f"스킬 이름 규칙 위반: {name} (소문자 · 숫자 · 하이픈, 1~64자, 하이픈으로 시작/끝 · -- 금지)")
    if ":" in name:
        raise ValueError("스킬 이름에 ':'는 넣지 않는다")


def load_sources() -> list[SkillSource]:
    out: list[SkillSource] = []
    for name in SKILL_NAMES:
        validate_name(name)
        base = resources.path(f"skills/{name}")
        text = (base / "SKILL.md").read_text(encoding="utf-8")
        doc = frontmatter.parse(text)
        if doc.meta.get("name") != name:
            raise ValueError(f"{name}/SKILL.md의 name이 폴더 이름과 다릅니다")
        extra = {}
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.name != "SKILL.md":
                extra[str(p.relative_to(base))] = p.read_text(encoding="utf-8")
        out.append(
            SkillSource(
                name=name,
                description=str(doc.meta.get("description", "")).strip(),
                invocation=str(doc.meta.get("invocation", "model")),
                argument_hint=str(doc.meta.get("argument-hint", "") or ""),
                body=doc.body.lstrip("\n"),
                extra=extra,
            )
        )
    return out


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(_flatten(v, key))
            out[key] = v
    return out


def body_context(profile: Profile, tool: str, enums: enums_mod.Enums | None = None) -> dict[str, Any]:
    data = dict(profile.data)
    data["knowledge"] = profile.knowledge  # with defaults (write: direct …)
    # <<debt_status.resolved>> · <<idea_status.dropped.label>> — status names come from enums.yaml only
    ctx: dict[str, Any] = dict((enums or enums_mod.load()).context())
    ctx.update(_flatten(data))
    ctx["tool"] = tool
    ctx["knowledge"] = bool(profile.knowledge)
    ctx["team"] = profile.team
    return ctx


def rewrite_commands(text: str, prefix: str) -> str:
    """`/l-build` → the tool's calling form (`$l-build` for Codex)."""
    return text if prefix == "/" else CMD_RE.sub(lambda m: prefix + m.group(1), text)


def render_body(src: SkillSource, profile: Profile, tool: Tool, prefix: str, enums: enums_mod.Enums | None = None) -> str:
    ctx = body_context(profile, tool.name, enums)
    body = rewrite_commands(templating.apply_conditions(src.body, ctx), prefix)
    body = body.replace(SESSION_TOKEN, tool.session_expr)
    if not tool.expands_arguments:
        body = body.replace("`$ARGUMENTS`", "사용자가 명령과 함께 준 입력").replace("$ARGUMENTS", "사용자 입력")
    # <<plan.max_questions>> → the project's current answer (lantern upgrade re-renders on change)
    return PROFILE_TOKEN.sub(lambda m: _token_value(ctx.get(m.group(1))), body)


def _token_value(value: Any) -> str:
    if value is None or value == "":
        return "(없음)"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "(없음)"
    return str(value)


def command_prefix(tools: list[Tool]) -> str:
    """Tools that share a skill folder (Codex · Antigravity: .agents/skills) get one calling form;
    if they disagree, `/` is used and AGENTS.md tells Codex to read it as `$`."""
    prefixes = {t.command_prefix for t in tools}
    return prefixes.pop() if len(prefixes) == 1 else "/"


def generate(profile: Profile, tools: list[Tool], enums: enums_mod.Enums | None = None) -> dict[str, str]:
    by_root: dict[str, list[Tool]] = {}
    for t in tools:
        by_root.setdefault(t.skill_root, []).append(t)
    files: dict[str, str] = {}
    for src in load_sources():
        for group in by_root.values():
            prefix = command_prefix(group)
            for t in group:
                for rel, text in t.skill_files(src, profile, prefix, enums).items():
                    if rel in files and files[rel] != text:
                        raise ValueError(f"{rel}: 같은 폴더를 쓰는 도구들이 서로 다른 내용을 만듭니다")
                    files[rel] = text
    return files
