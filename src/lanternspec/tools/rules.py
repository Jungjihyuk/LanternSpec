"""AGENTS.md — the one rules file every tool reads (Claude Code too; an existing CLAUDE.md imports it).

Our rules live between `<!-- lanternspec:start -->` and `<!-- lanternspec:end -->`; the rest of
the file belongs to the project.

Not here:
    - choosing the principles → core/principles.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import resources
from ..core import principles, templating
from ..core.profile import Profile
from ..core.project import Project, worktree_files
from .skills import PROFILE_TOKEN, body_context, command_prefix, rewrite_commands

if TYPE_CHECKING:
    from ..core.enums import Enums
    from .base import Tool

AGENTS_START, AGENTS_END = "<!-- lanternspec:start -->", "<!-- lanternspec:end -->"
PRINCIPLES_SLOT = "<!-- lantern:principles -->"


def agents_block(profile: Profile, tools: list[Tool], enums: Enums | None = None) -> str:
    """Render our AGENTS.md block: the rules source filled with profile values, plus the design principles.

    Args:
        profile: The project's settings.
        tools: The installed tools (they decide the command form).
        enums: The project's choice lists; the bundled ones when None.

    Returns:
        The block, with its start and end marks.

    Example:
        >>> from lanternspec.tools import get
        >>> agents_block(Profile(data={}), [get("claude")]).splitlines()[0]
        '<!-- lanternspec:start -->'
    """
    text = resources.read_text(f"locales/{profile.language}/agents/AGENTS.md")
    ctx = body_context(profile, "agents", enums)
    text = rewrite_commands(templating.apply_conditions(text, ctx), command_prefix(tools))
    text = PROFILE_TOKEN.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), text)
    section = "\n\n".join(x for x in (principles_section(profile), parts_section(profile)) if x)
    text = text.replace(f"\n{PRINCIPLES_SLOT}\n", f"\n{section}\n" if section else "")
    return f"{AGENTS_START}\n{text.strip()}\n{AGENTS_END}"


def merge_block(existing: str, block: str) -> str:
    r"""Put our block into an AGENTS.md text: replace the old block, or add it at the end.

    Args:
        existing: The current AGENTS.md text ("" when missing).
        block: Our block.

    Returns:
        The new text; the project's own lines stay as written.

    Example:
        >>> merge_block("# 우리 규칙\n", "<!-- lanternspec:start -->\n…\n<!-- lanternspec:end -->")
        '# 우리 규칙\n\n<!-- lanternspec:start -->\n…\n<!-- lanternspec:end -->\n'
    """
    s, e = existing.find(AGENTS_START), existing.find(AGENTS_END)
    if s != -1 and e != -1 and e > s:
        return existing[:s] + block + existing[e + len(AGENTS_END) :]
    if existing.strip():
        return existing.rstrip() + "\n\n" + block + "\n"
    return "# AGENTS.md\n\n" + block + "\n"


def principles_section(profile: Profile) -> str:
    """Build the design principles and code conventions for the AGENTS.md block — essentials only.

    Details live in the design-principles document.

    Args:
        profile: The project's settings.

    Returns:
        The section; "" when the project kind is not set.

    Example:
        >>> principles_section(Profile(data={}))
        ''
    """
    sel = principles.select(profile)
    if sel is None:
        return ""
    t = principles.table(profile.language)
    names, say = t["levels"], t["agents"]
    doc = f"{profile.docs_root}/{profile.names.folder('rules')}/{profile.names.file('principles')}"
    lines = [say["principles_title"].format(summary=sel.summary()), say["details"].format(doc=doc)]
    for level in ("must", "should"):
        chosen = sel.at(level)
        if chosen:
            lines.append(f"- **{names[level]}:** " + " · ".join(p.name for p in chosen))
    lines.append(f"- {t['priority']}")
    lines.append(f"- **{say['ways_of_working']}:** " + " · ".join(name for name, _ in sel.always))
    if sel.conventions and not active_parts(profile):  # with parts, conventions and checks live in each part's AGENTS.md
        lines += ["", say["conventions_title"].format(languages=" · ".join(c.label for c in sel.conventions))]
        cmds = [(principles.role_label(r, profile.language), profile.get(f"build.{r}")) for r in (*principles.COMMAND_ROLES, "test")]
        cmds = [f"{label} `{cmd}`" for label, cmd in cmds if cmd]
        if cmds:
            lines.append("- " + say["checks"].format(commands=" · ".join(cmds)))
        language = principles.comment_languages(profile.language).get(profile.comment_language, profile.comment_language)
        for c in sel.conventions:
            prefix = f"{c.label} " if len(sel.conventions) > 1 else ""
            lines.append(f"- {prefix}{principles.rule_label('type_hints', profile.language)}: {c.rules['type_hints']}")
            lines.append(f"- {prefix}{principles.rule_label('docs', profile.language)} ({c.docs_style} · {language}): {c.rules['docs']}")
    return "\n".join(lines)


def nested_agents(project: Project) -> list[str]:
    """List the AGENTS.md files below the project root (tracked or new, not ignored, not deleted).

    Args:
        project: The project.

    Returns:
        Paths relative to the root, e.g. "backend/app/AGENTS.md".

    Example:
        >>> nested_agents(project)  # doctest: +SKIP
        ['backend/app/AGENTS.md']
    """
    return sorted(worktree_files(project.root, "*/AGENTS.md"))


def active_parts(profile: Profile) -> list[dict[str, Any]]:
    """The parts that get their own AGENTS.md — only when there are two or more (one part is the whole project).

    Args:
        profile: The project's settings (code.parts).

    Returns:
        The recorded parts, or [] with fewer than two.

    Example:
        >>> active_parts(Profile(data={"code": {"parts": [{"path": "backend"}]}}))
        []
    """
    parts = [p for p in profile.get("code.parts") or [] if isinstance(p, dict) and p.get("path")]
    return parts if len(parts) >= 2 else []


def parts_section(profile: Profile) -> str:
    """Build the map of parts for the root AGENTS.md block.

    Args:
        profile: The project's settings.

    Returns:
        The section; "" without two or more parts.

    Example:
        >>> data = {"code": {"parts": [{"path": "api", "languages": ["python"]}, {"path": "web", "languages": ["typescript"]}]}}
        >>> parts_section(Profile(data=data)).splitlines()[3]
        '| `api` | Python | `api/AGENTS.md` |'
    """
    parts = active_parts(profile)
    if not parts:
        return ""
    say = principles.table(profile.language)["agents"]
    lines = [say["parts_title"], say["parts_header"], "|---|---|---|"]
    for part in parts:
        labels = " · ".join(c.label for c in principles.conventions_for(profile, list(part.get("languages") or []))) or "-"
        lines.append(f"| `{part['path']}` | {labels} | `{part['path']}/AGENTS.md` |")
    lines.append(f"- {say['parts_rule']}")
    return "\n".join(lines)


def part_block(profile: Profile, part: dict[str, Any]) -> str:
    """Render the block of one part's AGENTS.md: its language conventions and its own check commands.

    Args:
        profile: The project's settings.
        part: The part as recorded in lantern.yaml (path · languages · build).

    Returns:
        The block, with its start and end marks.

    Example:
        >>> block = part_block(Profile(data={}), {"path": "api", "languages": ["python"], "build": {"lint": "uv run ruff check ."}})
        >>> block.splitlines()[1], "`uv run ruff check .`" in block
        ('## 영역 api — 이 폴더의 규칙', True)
    """
    lang = profile.language
    t = principles.table(lang)
    say = t["agents"]
    lines = [say["part_title"].format(path=part["path"]), "", say["part_root"]]
    convs = principles.conventions_for(profile, list(part.get("languages") or []))
    if convs:
        lines += ["", say["conventions_title"].format(languages=" · ".join(c.label for c in convs))]
    build = part.get("build") or {}
    cmds = [f"{principles.role_label(r, lang)} `{build[r]}`" for r in (*principles.COMMAND_ROLES, "test") if build.get(r)]
    if cmds:
        lines.append("- " + say["part_checks"].format(commands=" · ".join(cmds)))
    comment = principles.comment_languages(lang).get(profile.comment_language, profile.comment_language)
    for c in convs:
        prefix = f"{c.label} " if len(convs) > 1 else ""
        lines.append(f"- {prefix}{principles.rule_label('type_hints', lang)}: {c.rules['type_hints']}")
        lines.append(f"- {prefix}{principles.rule_label('docs', lang)} ({c.docs_style} · {comment}): {c.rules['docs']}")
    return f"{AGENTS_START}\n" + "\n".join(lines) + f"\n{AGENTS_END}"


def remove_block(text: str) -> str:
    r"""Take our block out of an AGENTS.md text; the person's own lines stay.

    Args:
        text: The AGENTS.md text.

    Returns:
        The text without the block ("" when nothing else was in it).

    Example:
        >>> remove_block("# 우리 규칙\n\n<!-- lanternspec:start -->\n…\n<!-- lanternspec:end -->\n")
        '# 우리 규칙\n'
    """
    s, e = text.find(AGENTS_START), text.find(AGENTS_END)
    if s == -1 or e < s:
        return text
    rest = (text[:s].rstrip("\n") + "\n" + text[e + len(AGENTS_END) :].lstrip("\n")).strip("\n")
    return rest + "\n" if rest and rest != "# AGENTS.md" else ""
