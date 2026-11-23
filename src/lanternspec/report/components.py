"""Show what the AI tool started with (MCP servers, plugins, skills, hooks) and how often the MCP tools among them were called.

Responsibilities:
    - join each session's component list with the tool calls of that session's turns
    - list what was added or removed between one session's list and the next

Not here:
    - reading the AI tool's settings files that name the components → tools/<tool>.py (Tool.components)
    - writing the session line → tools/agent_hooks.py · tools/runlog.py
    - the report that prints this → report/evaluate.py
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..core.enums import Enums

KINDS = ("mcp", "plugin", "skill", "hook")
CALL_KINDS = ("mcp", "plugin")  # kinds whose tool calls can be tied to them (an MCP tool's name says which server it came from)


def kind_label(kind: str, enums: Enums) -> str:
    """Return the name of a component kind as people read it (from the `component_kind` list of enums.yaml).

    Args:
        kind: A kind kept in the run log (`mcp` · `plugin` · `skill` · `hook`).
        enums: The project's choice lists.

    Returns:
        The kind's name in the project's language; the kind itself when it is not a known one.

    Example:
        >>> from lanternspec.core.enums import load
        >>> kind_label("mcp", load())
        'MCP 서버'
    """
    try:
        return enums.value("component_kind", kind)
    except (KeyError, LookupError):
        return kind


def other_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count the components of the kinds whose calls can't be told, one number per kind (they are not worth a row each).

    Args:
        rows: `usage()["rows"]`.

    Returns:
        Kind → how many different names were listed, for the kinds not in CALL_KINDS; kinds with none are left out.

    Example:
        >>> other_counts([{"kind": "skill", "name": "a"}, {"kind": "skill", "name": "b"}, {"kind": "mcp", "name": "q"}])
        {'skill': 2}
    """
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS if k not in CALL_KINDS}
    return {k: n for k, n in counts.items() if n}


def _listed(components: Any) -> dict[str, list[str]]:
    """A session's list as kind → names; anything that is not that shape reads as empty."""
    if not isinstance(components, dict):
        return {}
    return {k: [str(n) for n in v] for k, v in components.items() if isinstance(v, list)}


def _flat(components: dict[str, list[str]]) -> set[tuple[str, str]]:
    return {(kind, name) for kind, names in components.items() for name in names}


def _order(item: tuple[str, str]) -> tuple[int, str]:
    return (KINDS.index(item[0]) if item[0] in KINDS else len(KINDS), item[1])


def usage(runs: list[dict[str, Any]]) -> dict[str, Any]:
    r"""Summarize the components the sessions listed, how often their MCP tools were called, and what changed between sessions.

    Sessions written before the list was kept have none and are left out. A kind whose calls can't be told
    (skills, hooks) or a session whose tool is not known has no count (None), which is not the same as 0.

    Args:
        runs: The run log's records, oldest first.

    Returns:
        `rows`: one per component with its sessions, sessions with a call and calls; `changes`: what was added or
        removed from one session's list to the next, with the start of the later session; `unlisted`: the sessions
        and turns that have no list (so their calls are in no row), such as a session an older lantern logged.

    Example:
        >>> runs = [
        ...     {"kind": "session", "session": "a", "start": "t1", "harness": "claude", "components": {"mcp": ["qmd", "x"]}},
        ...     {"kind": "turn", "session": "a", "tools": {"mcp__qmd__query": 3}},
        ...     {"kind": "session", "session": "b", "start": "t2", "harness": "claude", "components": {"mcp": ["qmd"]}},
        ... ]
        >>> out = usage(runs)
        >>> [(r["name"], r["sessions"], r["calls"]) for r in out["rows"]]
        [('qmd', 2, 3), ('x', 1, 0)]
        >>> out["changes"]
        [{'at': 't2', 'change': 'removed', 'kind': 'mcp', 'name': 'x'}]
        >>> out["unlisted"]
        {'sessions': 0, 'turns': 0}
    """
    from ..tools import get

    sessions = [r for r in runs if r.get("kind") == "session" and "components" in r]
    tools_of: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in runs:
        if r.get("kind") == "turn":
            for name, n in (r.get("tools") or {}).items():
                tools_of[str(r.get("session"))][name] += int(n)

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for s in sessions:
        listed = _listed(s["components"])
        try:
            tool = get(str(s.get("harness") or ""))
        except ValueError:
            tool = None
        calls: dict[tuple[str, str], int] = defaultdict(int)
        if tool:
            for name, n in tools_of[str(s.get("session"))].items():
                if owner := tool.call_component(name, listed):
                    calls[owner] += n
        for item in _flat(listed):
            row = seen.setdefault(item, {"kind": item[0], "name": item[1], "sessions": 0, "sessions_with_calls": None, "calls": None})
            row["sessions"] += 1
            if tool and item[0] in CALL_KINDS:
                row["calls"] = (row["calls"] or 0) + calls[item]
                row["sessions_with_calls"] = (row["sessions_with_calls"] or 0) + (1 if calls[item] else 0)

    changes = []
    for before, after in zip(sessions, sessions[1:], strict=False):
        old, new = _flat(_listed(before["components"])), _flat(_listed(after["components"]))
        for change, items in (("removed", old - new), ("added", new - old)):
            changes += [{"at": after.get("start"), "change": change, "kind": k, "name": n} for k, n in sorted(items, key=_order)]
    listed_ids = {str(s.get("session")) for s in sessions}
    unlisted = [str(r.get("session")) for r in runs if r.get("kind") == "turn" and str(r.get("session")) not in listed_ids]
    return {
        "rows": [seen[k] for k in sorted(seen, key=_order)],
        "changes": changes,
        "unlisted": {"sessions": len(set(unlisted)), "turns": len(unlisted)},
    }
