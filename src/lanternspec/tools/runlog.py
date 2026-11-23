"""Run log `.lantern/runs.jsonl` — the raw material for the AI work evaluation (`lantern eval`).

Writers, one format, one line per `kind`:
* agent hooks, `session`: once per conversation — the tool and its version, LanternSpec's version, the settings repository's commit
* agent hooks, `turn`: per turn — start · end · model · skill · tool counts (the calls that worked) · failed tool calls · tokens
* agent hooks, `subagent`: per sub-agent call — name · start · end · model · tokens
* `lantern review` and the reviewer's stop hook, `review`: one line per review round — model · items · issues
* `lantern close <skill>`, `skill`: tools without agent hooks still leave one line per skill run
* agent hooks, `skill_time`: per skill run — from the `/l-…` prompt that started it to its `lantern close`, with the time
  the AI worked (the turns added up; the waits for the person between turns are left out) · tool calls · tokens
* the build loop, `loop`: where a loop starts (`event: start`, the settings and the base commit it runs with) and where
  each round ends (`event: end`); `attempt`: one line per try at one acceptance criterion. `lantern loop` writes them
  from what it measured — the agent never states a result itself

Per-session state between hook calls lives in `.lantern/runs-state/`.

Not here:
    - reading the log → report/evaluate.py
"""

from __future__ import annotations

import datetime as _dt
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


def _seconds(start: str | None, end: str | None) -> int:
    """Whole seconds from one run-log time to another; 0 when either is missing or unreadable."""
    if not start or not end:
        return 0
    try:
        return max(0, round((_dt.datetime.fromisoformat(end) - _dt.datetime.fromisoformat(start)).total_seconds()))
    except ValueError:
        return 0


def _open_run(data: dict[str, Any], skill: str, restart: bool) -> None:
    """Start the skill run this session is in, unless one is already open (a prompt names a new skill: `restart`)."""
    if restart or not data.get("run"):
        data["run"] = {"skill": skill, "start": data.get("start") or now_iso(), "worked": 0, "tool_calls": 0, "tokens": {}}


def _closes(tool_input: dict[str, Any] | None) -> tuple[str, str] | None:
    """Find a `lantern close <skill> [--work <id>]` command in a tool's input, whatever the tool calls its fields."""
    parts = [" ".join(map(str, v)) if isinstance(v, list) else str(v) for v in (tool_input or {}).values()]
    m = re.search(r"\blantern\s+close\s+(l-[a-z]+)\b([^\n;&|]*)", " ".join(parts))
    if not m:
        return None
    work = re.search(r"--work[\s=]+(\S+)", m.group(2))
    return m.group(1), work.group(1).strip("\"'") if work else ""


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


def session_start(project: Project, session: str, model: str | None, source: str = "", harness: dict[str, Any] | None = None) -> None:
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
        _open_run(data, m.group(1), restart=True)  # a run the person left open is dropped, not guessed at
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
            _open_run(data, name, restart=False)
    closing, run = _closes(tool_input), data.get("run")
    if closing and run and closing[0] == run["skill"]:  # another skill's close inside this run does not end it
        run["closed"] = {"at": now_iso(), "work": closing[1]}
    _save(project, session, data)


def tool_failed(project: Project, session: str, tool_name: str) -> None:
    """Count one tool call that ran and failed (a call the person refused or cancelled is not one).

    Args:
        project: The project.
        session: The conversation.
        tool_name: The tool that failed.

    Example:
        >>> tool_failed(project, "s1", "mcp__qmd__query")  # doctest: +SKIP
    """
    data = _load(project, session)
    if not data.get("start"):
        data["start"] = now_iso()
    failures = Counter(data.get("failures") or {})
    failures[tool_name or "?"] += 1
    data["failures"] = dict(failures)
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
    if not data.get("start") and not data.get("tools") and not data.get("failures"):
        return None
    end = now_iso()
    record = {
        "kind": "turn",
        "source": "hook",
        "session": session,
        "start": data.get("start"),
        "end": end,
        "model": data.get("model"),
        "skill": data.get("skill"),
        "tools": data.get("tools") or {},
        "tool_calls": sum((data.get("tools") or {}).values()),
    }
    if data.get("failures"):
        record["failures"] = data["failures"]
    if tokens:
        record["tokens"] = tokens
    append(project, record)
    run = _add_turn_to_run(project, session, data, record, end, tokens)
    # next turn starts fresh; the model is kept for the session, and so are the sub-agents still running and the open skill run
    _save(
        project,
        session,
        {
            "session": session,
            "start": None,
            "model": data.get("model"),
            "skill": None,
            "tools": {},
            "failures": {},
            "subagents": data.get("subagents") or {},
            **({"run": run} if run else {}),
        },
    )
    return record


def _add_turn_to_run(
    project: Project, session: str, data: dict[str, Any], record: dict[str, Any], end: str, tokens: dict[str, int] | None
) -> dict[str, Any] | None:
    """Add a finished turn to the open skill run; when the turn closed it, write the run's line.

    A turn that closed the run counts only up to the `lantern close`, so the AI's time never runs past the run's end.

    Returns:
        The run to keep open; None when there was none or this turn closed it.
    """
    run = data.get("run")
    if not run:
        return None
    closed = run.get("closed")
    run["worked"] += _seconds(data.get("start"), closed["at"] if closed else end)
    run["tool_calls"] += record["tool_calls"]
    for key, n in (tokens or {}).items():
        run["tokens"][key] = run["tokens"].get(key, 0) + n
    if not closed:
        return run
    line = {
        "kind": "skill_time",
        "source": "hook",
        "session": session,
        "skill": run["skill"],
        "work": closed["work"],
        "model": record["model"],
        "start": run["start"],
        "end": closed["at"],
        "worked": run["worked"],
        "tool_calls": run["tool_calls"],
    }
    append(project, line | ({"tokens": run["tokens"]} if run["tokens"] else {}))
    return None


def subagent_start(project: Project, session: str, agent_id: str, agent: str) -> None:
    """Remember when a sub-agent started, until it stops.

    Args:
        project: The project.
        session: The conversation.
        agent_id: The sub-agent's own ID.
        agent: Its name.

    Example:
        >>> subagent_start(project, "s1", "agent-1", "lantern-reviewer")  # doctest: +SKIP
    """
    data = _load(project, session)
    data.setdefault("subagents", {})[agent_id] = {"agent": agent, "start": now_iso()}
    _save(project, session, data)


def subagent_stop(
    project: Project, session: str, agent_id: str, agent: str, model: str | None, tokens: dict[str, int] | None
) -> dict[str, Any]:
    """Write one sub-agent call: its name, when it started and ended, the model and the tokens it spent.

    Args:
        project: The project.
        session: The conversation.
        agent_id: The sub-agent's own ID.
        agent: Its name.
        model: The model it ran on, when its transcript said.
        tokens: What it spent (`Tool.agent_usage`); left out when the tool doesn't say.

    Returns:
        The record.

    Example:
        >>> subagent_stop(project, "s1", "agent-1", "lantern-reviewer", "claude-opus-5-5", None)["kind"]  # doctest: +SKIP
        'subagent'
    """
    data = _load(project, session)
    began = (data.get("subagents") or {}).pop(agent_id, {})
    _save(project, session, data)
    record: dict[str, Any] = {
        "kind": "subagent",
        "source": "hook",
        "session": session,
        "agent_id": agent_id,
        "agent": agent or began.get("agent"),
        "start": began.get("start"),
        "end": now_iso(),
        "model": model or None,
    }
    if tokens:
        record["tokens"] = tokens
    append(project, record)
    return record


def review_pack(project: Project, work: str, items: int) -> dict[str, Any]:
    """Write that a review pack was made for a work and asks the reviewer about this many items.

    A round is recorded only against a pack that waits for an answer, and only when it judges every item.

    Args:
        project: The project.
        work: The work.
        items: How many items the pack asks about.

    Returns:
        The record.

    Example:
        >>> review_pack(project, "W-012", 5)["kind"]  # doctest: +SKIP
        'review_pack'
    """
    record = {"kind": "review_pack", "source": "cli", "at": now_iso(), "work": work, "items": items}
    append(project, record)
    return record


def review(
    project: Project, work: str, run: str, model: str, items: int, issue_list: list[str], unsupported: int, source: str
) -> dict[str, Any]:
    """Write one review round: what the reviewer judged, and the issues it found, in its own words.

    Args:
        project: The project.
        work: The work reviewed.
        run: The run the round belongs to (the loop run, else the review's own).
        model: The reviewer's model; "" when unknown.
        items: How many items were judged.
        issue_list: What the issues said.
        unsupported: How many of them name no `path:line`.
        source: "hook" or "cli".

    Returns:
        The record.

    Example:
        >>> review(project, "W-012", "r1", "opus", 5, [], 0, "hook")["issues"]  # doctest: +SKIP
        0
    """
    record = {
        "kind": "review",
        "source": source,
        "at": now_iso(),
        "work": work,
        "run": run,
        "review_model": model,
        "items": items,
        "issues": len(issue_list),
        "issue_list": issue_list,
        "unsupported": unsupported,
    }
    append(project, record)
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
