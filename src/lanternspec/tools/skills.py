"""One skill source (Agent Skills standard, resources/skills) → each tool's skill files.

Rendering is tool-agnostic: profile values and conditions are filled in here; a tool adapter
only says where the files go and what frontmatter they carry (tools/<tool>.py).

Marks in a skill source:
    - `<<dotted.key>>` — a lantern.yaml value or an enum name by role, e.g. `<<debt_status.resolved>>`
    - `<<SESSION_ID>>` — the tool's session expression
    - `lantern:if` blocks — kept only when the profile matches (core/templating.py)
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
    """One skill as written in resources/skills.

    Attributes:
        name: The skill name, e.g. "l-build".
        description: When to use it (the model reads this to decide).
        invocation: "model", "manual", or "profile:<dotted key>" (manual when that setting is "manual").
        argument_hint: Hint for the skill's argument, e.g. "W-012".
        body: The skill body, before rendering.
        extra: Other files of the skill folder: relative path → text.

    Example:
        >>> src = next(s for s in load_sources() if s.name == "l-idea")
        >>> src.invocation
        'profile:idea.capture'
    """

    name: str
    description: str
    invocation: str  # model | manual | profile:<dotted key>
    argument_hint: str
    body: str
    extra: dict[str, str] = field(default_factory=dict)  # relative path -> text (references/…)

    def manual_only(self, profile: Profile) -> bool:
        """Tell whether the skill runs only when the user calls it (never chosen by the model).

        Args:
            profile: The project's settings.

        Returns:
            True for manual skills, and for profile-bound skills whose setting is "manual".

        Example:
            >>> src = next(s for s in load_sources() if s.name == "l-idea")
            >>> src.manual_only(Profile(data={"idea": {"capture": "manual"}}))
            True
        """
        if self.invocation == "manual":
            return True
        if self.invocation.startswith("profile:"):
            return str(profile.get(self.invocation.split(":", 1)[1])) == "manual"
        return False


def validate_name(name: str) -> None:
    """Check a skill name against the Agent Skills naming rules.

    Args:
        name: The skill name.

    Raises:
        ValueError: The name breaks a rule (lower case, digits and hyphens, 1–64 characters,
            no leading, trailing or double hyphen).

    Example:
        >>> validate_name("l-build")
        >>> validate_name("L_Build")
        Traceback (most recent call last):
        ...
        ValueError: 스킬 이름 규칙 위반: L_Build (소문자 · 숫자 · 하이픈, 1~64자, 하이픈으로 시작/끝 · -- 금지)
    """
    if not NAME_RE.match(name):
        raise ValueError(f"스킬 이름 규칙 위반: {name} (소문자 · 숫자 · 하이픈, 1~64자, 하이픈으로 시작/끝 · -- 금지)")
    if ":" in name:
        raise ValueError("스킬 이름에 ':'는 넣지 않는다")


def load_sources() -> list[SkillSource]:
    """Read every skill source bundled with the package.

    Returns:
        One source per name in SKILL_NAMES, in that order.

    Raises:
        ValueError: A name breaks the rules or does not match its folder.

    Example:
        >>> [s.name for s in load_sources()][:3]
        ['l-init', 'l-idea', 'l-plan']
    """
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
    """Collect the values skill bodies and the AGENTS.md block are filled with.

    Args:
        profile: The project's settings.
        tool: The tool name (or "agents" for AGENTS.md).
        enums: The project's choice lists; the bundled ones when None.

    Returns:
        Enum names by role, every lantern.yaml value by dotted key, and tool, knowledge and team.

    Example:
        >>> ctx = body_context(Profile(data={"plan": {"max_questions": 3}}), "claude")
        >>> ctx["plan.max_questions"], ctx["debt_status.resolved"], ctx["tool"]
        (3, '해결', 'claude')
    """
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
    """Rewrite `/l-…` skill calls into the tool's calling form (`$l-build` for Codex).

    Args:
        text: Any text.
        prefix: The tool's command prefix.

    Returns:
        The rewritten text.

    Example:
        >>> rewrite_commands("다음: /l-build W-012 (경로 a/l-build는 그대로)", "$")
        '다음: $l-build W-012 (경로 a/l-build는 그대로)'
    """
    return text if prefix == "/" else CMD_RE.sub(lambda m: prefix + m.group(1), text)


def render_body(src: SkillSource, profile: Profile, tool: Tool, prefix: str, enums: enums_mod.Enums | None = None) -> str:
    """Render a skill body for one tool: conditions, command form, session expression, `$ARGUMENTS`, profile values.

    Args:
        src: The skill source.
        profile: The project's settings.
        tool: The tool.
        prefix: The command prefix to use.
        enums: The project's choice lists; the bundled ones when None.

    Returns:
        The body as the tool will read it.

    Example:
        >>> from lanternspec.tools import get
        >>> src = next(s for s in load_sources() if s.name == "l-plan")
        >>> "<<" in render_body(src, Profile(data={}), get("codex"), "$")
        False
    """
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
    """Pick one calling form for tools that share a skill folder.

    Codex and Antigravity both use `.agents/skills`; if they disagree, "/" is used and
    AGENTS.md tells Codex to read it as "$".

    Args:
        tools: Tools that share a skill folder.

    Returns:
        The prefix.

    Example:
        >>> from lanternspec.tools import get
        >>> command_prefix([get("codex")]), command_prefix([get("codex"), get("antigravity")])
        ('$', '/')
    """
    prefixes = {t.command_prefix for t in tools}
    return prefixes.pop() if len(prefixes) == 1 else "/"


def generate(profile: Profile, tools: list[Tool], enums: enums_mod.Enums | None = None) -> dict[str, str]:
    """Build every skill file for the chosen tools.

    Args:
        profile: The project's settings.
        tools: The tools to install for.
        enums: The project's choice lists; the bundled ones when None.

    Returns:
        Path relative to the project root → text.

    Raises:
        ValueError: Tools sharing a folder would write different content to the same file.

    Example:
        >>> from lanternspec.tools import get
        >>> files = generate(Profile(data={}), [get("claude")])
        >>> ".claude/skills/l-build/SKILL.md" in files
        True
    """
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
