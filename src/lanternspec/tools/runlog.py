"""Run log `.lantern/runs.jsonl` — the raw material for evaluation. For now it only accumulates.

Two writers, one format:
* agent hooks: per turn — start · end · model · skill · tool counts
* `lantern close <skill>`: tools without agent hooks still leave one line per skill run

Per-session state between hook calls lives in `.lantern/runs-state/`.

Not here:
    - reading the log → report/evaluate.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..core.project import Project, now_iso
from ..core.state import ensure_state_dir

RUNS = "runs.jsonl"


def _state_file(project: Project, session: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", session or "unknown")[:80]
    return project.state / "runs-state" / f"{safe}.json"


def append(project: Project, record: dict[str, Any]) -> None:
    """Append one record to the run log.

    Args:
        project: The project.
        record: The record (written as one JSON line, sorted keys).

    Example:
        >>> append(project, {"kind": "skill", "skill": "l-build"})  # doctest: +SKIP
    """
    ensure_state_dir(project)
    with (project.state / RUNS).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _load(project: Project, session: str) -> dict[str, Any]:
    p = _state_file(project, session)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"session": session, "start": None, "model": None, "skill": None, "tools": {}}


def _save(project: Project, session: str, data: dict[str, Any]) -> None:
    p = _state_file(project, session)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def session_start(project: Project, session: str, model: str | None, source: str = "") -> None:
    """Remember the model and how the session started.

    Args:
        project: The project.
        session: The conversation.
        model: The model, when the tool sent it.
        source: "startup", "resume" or "compact".

    Example:
        >>> session_start(project, "s1", "claude-opus-5-5", "startup")  # doctest: +SKIP
    """
    data = _load(project, session)
    if model:
        data["model"] = model
    data["source"] = source
    _save(project, session, data)


def prompt(project: Project, session: str, text: str) -> None:
    """Mark the start of a turn and which skill (`/l-…` or `$l-…`) started it.

    Args:
        project: The project.
        session: The conversation.
        text: The user's message.

    Example:
        >>> prompt(project, "s1", "/l-build W-012")  # doctest: +SKIP
    """
    data = _load(project, session)
    if not data.get("start"):
        data["start"] = now_iso()
    m = re.match(r"\s*[/$](l-[a-z]+)\b", text or "")
    if m:
        data["skill"] = m.group(1)
    _save(project, session, data)


def tool(project: Project, session: str, tool_name: str, tool_input: dict | None = None) -> None:
    """Count one tool call (a Skill call also names the turn's skill).

    Args:
        project: The project.
        session: The conversation.
        tool_name: The tool that ran.
        tool_input: Its input.

    Example:
        >>> tool(project, "s1", "Edit")  # doctest: +SKIP
    """
    data = _load(project, session)
    if not data.get("start"):
        data["start"] = now_iso()
    tools = Counter(data.get("tools") or {})
    tools[tool_name or "?"] += 1
    data["tools"] = dict(tools)
    if tool_name == "Skill" and tool_input:
        name = str(tool_input.get("skill") or tool_input.get("command") or "")
        if name.startswith("l-"):
            data["skill"] = name
    _save(project, session, data)


def stop(project: Project, session: str, model: str | None = None) -> dict[str, Any] | None:
    """Write the turn's record and start the next turn fresh (the model is kept).

    Args:
        project: The project.
        session: The conversation.
        model: The model, when the tool sent it now.

    Returns:
        The record; None when nothing happened in the turn.

    Example:
        >>> stop(project, "s1")["tool_calls"]  # doctest: +SKIP
        4
    """
    data = _load(project, session)
    if model:
        data["model"] = model
    if not data.get("start") and not data.get("tools"):
        return None
    record = {
        "kind": "turn",
        "source": "hook",
        "session": session,
        "start": data.get("start"),
        "end": now_iso(),
        "model": data.get("model"),
        "skill": data.get("skill"),
        "tools": data.get("tools") or {},
        "tool_calls": sum((data.get("tools") or {}).values()),
    }
    append(project, record)
    # next turn starts fresh; the model is kept for the session
    _save(project, session, {"session": session, "start": None, "model": data.get("model"), "skill": None, "tools": {}})
    return record


def skill_run(project: Project, skill: str, start: str | None, model: str | None, extra: dict[str, Any]) -> dict[str, Any]:
    """Write one skill-run record (from `lantern close`).

    Args:
        project: The project.
        skill: The skill.
        start: When it started.
        model: The model in use.
        extra: More fields, e.g. work, check counts and the configuration.

    Returns:
        The record.

    Example:
        >>> skill_run(project, "l-build", None, None, {"work": "W-012"})["kind"]  # doctest: +SKIP
        'skill'
    """
    record = {"kind": "skill", "source": "close", "skill": skill, "start": start, "end": now_iso(), "model": model, **extra}
    append(project, record)
    return record
