"""Run log `.lantern/runs.jsonl` — the raw material for the AI work evaluation (`lantern eval`).

Writers, one format, one line per `kind`:
* agent hooks, `session`: once per conversation — the tool and its version, LanternSpec's version, the settings repository's commit
* agent hooks, `turn`: per turn — start · end · model · skill · tool counts · tokens
* `lantern close <skill>`, `skill`: tools without agent hooks still leave one line per skill run
* the build loop, `loop`: where a loop starts (`event: start`, the settings and the base commit it runs with) and where
  each round ends (`event: end`); `attempt`: one line per try at one acceptance criterion. `lantern loop` writes them
  from what it measured — the agent never states a result itself

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


def session_start(project: Project, session: str, model: str | None, source: str = "", harness: dict[str, str] | None = None) -> None:
    """Remember the model and how the session started, and log the setup the session runs with.

    Args:
        project: The project.
        session: The conversation.
        model: The model, when the tool sent it.
        source: "startup", "resume" or "compact".
        harness: The setup (tool, versions, settings commit) to log as a `session` line; None logs nothing,
            e.g. after compaction, when it is the same session.

    Example:
        >>> session_start(project, "s1", "claude-opus-5-5", "startup", {"harness": "claude"})  # doctest: +SKIP
    """
    data = _load(project, session)
    if model:
        data["model"] = model
    data["source"] = source
    _save(project, session, data)
    if harness is not None:
        append(
            project, {"kind": "session", "source": "hook", "session": session, "start": now_iso(), "model": data.get("model"), **harness}
        )


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


def stop(project: Project, session: str, model: str | None = None, tokens: dict[str, int] | None = None) -> dict[str, Any] | None:
    """Write the turn's record and start the next turn fresh (the model is kept).

    Args:
        project: The project.
        session: The conversation.
        model: The model, when the tool sent it now.
        tokens: What the turn spent (`Tool.turn_tokens`); left out of the record when the tool doesn't say.

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
    if tokens:
        record["tokens"] = tokens
    append(project, record)
    # next turn starts fresh; the model is kept for the session
    _save(project, session, {"session": session, "start": None, "model": data.get("model"), "skill": None, "tools": {}})
    return record


def loop_attempt(
    project: Project,
    run: str,
    task: str,
    ac: str,
    attempt: int,
    result: str,
    failed_check: str = "",
    understood: bool | None = None,
    work: str = "",
    scope: str = "one",
) -> dict[str, Any]:
    """Write one attempt line: one try at one acceptance criterion in a build loop.

    Args:
        project: The project.
        run: The loop run it belongs to.
        task: The task being built.
        ac: The acceptance criterion tried.
        attempt: Which try this is, from 1.
        result: How it ended.
        failed_check: What failed, when it did not pass.
        understood: Whether the person said they understood the plan; None when it was not asked.
        work: The work the task belongs to.
        scope: "one" when only that criterion's test ran, "all" when the whole suite stood in for it.

    Returns:
        The record.

    Example:
        >>> loop_attempt(project, "r1", "T-3", "AC-2", 1, "pass")["kind"]  # doctest: +SKIP
        'attempt'
    """
    record = {
        "kind": "attempt",
        "source": "build",
        "at": now_iso(),
        "run": run,
        "work": work,
        "task": task,
        "ac": ac,
        "attempt": attempt,
        "result": result,
        "failed_check": failed_check,
        "understood": understood,
        "scope": scope,
    }
    append(project, record)
    return record


def loop_event(project: Project, event: str, run: str, work: str, **fields: Any) -> dict[str, Any]:
    """Write one loop line: a loop starting or a round ending.

    Args:
        project: The project.
        event: "start" or "end".
        run: The loop run it belongs to.
        work: The work being built.
        **fields: What was measured (start: mode · settings · base · tests; end: round · result · counts).

    Returns:
        The record.

    Example:
        >>> loop_event(project, "start", "r1", "W-012", mode="loop")["event"]  # doctest: +SKIP
        'start'
    """
    record = {"kind": "loop", "source": "build", "event": event, "at": now_iso(), "run": run, "work": work, **fields}
    append(project, record)
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
