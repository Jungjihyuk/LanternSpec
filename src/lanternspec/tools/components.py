"""Tell the AI about an MCP server or plugin the tool did not start with before, so a component card can say why it was added.

Responsibilities:
    - remember which MCP servers and plugins earlier conversations saw (`.lantern/components-seen.json`)
    - find which components already have a card
    - word the line handed to the AI at the start of a conversation

Not here:
    - reading the AI tool's settings → tools/<tool>.py (Tool.components)
    - making the card → work/scaffold.py
"""

from __future__ import annotations

import json
from typing import Any

from ..core import frontmatter
from ..core.messages import msg
from ..core.project import Project, read
from ..core.state import ensure_state_dir

ASKED_KINDS = ("mcp", "plugin")  # skills and hook events come and go with the person's own setup; a card for each would be noise
SEEN_FILE = "components-seen.json"


def _load(project: Project) -> set[str] | None:
    """The `kind:name` entries seen before; None when there is no usable file (the first conversation, or a broken file)."""
    try:
        data = json.loads((project.state / SEEN_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return {str(x) for x in data} if isinstance(data, list) else None


def _save(project: Project, seen: set[str]) -> None:
    ensure_state_dir(project)  # the file lists the person's own add-ons: its folder's .gitignore must cover it
    (project.state / SEEN_FILE).write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")


def _carded(project: Project) -> set[str]:
    """The names of the components that have a card in the decisions folder."""
    folder = project.folder("decisions")
    names: set[str] = set()
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        try:
            meta = frontmatter.parse(read(path)).meta
        except (OSError, UnicodeDecodeError):
            continue
        if meta.get("type") == "component" and meta.get("component"):
            names.add(str(meta["component"]))
    return names


def notice(project: Project, components: dict[str, list[str]]) -> str:
    r"""Say which MCP servers and plugins showed up since the last conversation and have no card yet.

    The first conversation only takes stock: what is already there is not asked about. After that each new one is
    named once (the conversation after it hears nothing, whether or not a card was made). Only MCP servers and
    plugins are named.

    Args:
        project: The project.
        components: What the tool lists now, kind → names (`Tool.components`).

    Returns:
        One line for each new component, for the AI to pass on; empty when there is nothing new.

    Example:
        >>> notice(project, {"mcp": ["qmd"]})  # doctest: +SKIP
        ''
    """
    now = {f"{kind}:{name}" for kind in ASKED_KINDS for name in components.get(kind, [])}
    seen = _load(project)
    if seen is None:
        _save(project, now)
        return ""
    new = sorted(now - seen)
    if not new:
        return ""
    carded = _carded(project)
    lines: list[str] = []
    for entry in new:
        kind, _, name = entry.partition(":")
        if name in carded:
            continue
        lines.append(_line(project, kind, name))
    _save(project, seen | now)  # last: one that could not be worded is told the next time
    return "\n".join(lines)


def _line(project: Project, role: str, name: str) -> str:
    """Word the line for one new component."""
    kind_name = project.enums.value("component_kind", role)
    return msg(
        "[LanternSpec] A new {kind} showed up in this tool: {name}. If it was added on purpose, ask the person once whether to leave "
        "a component card (why it was added, what it should achieve, what to measure): "
        'lantern scaffold component "{name}" --kind {role}',
        kind=kind_name,
        name=name,
        role=role,
    )


def safe_notice(project: Project, components: Any) -> str:
    """`notice`, but never raising: the hook must not stop the AI over a card suggestion."""
    try:
        return notice(project, components if isinstance(components, dict) else {})
    except (OSError, ValueError, LookupError, TypeError, AttributeError):
        return ""
