"""Is each AI tool's connection still working? Versions, hook runs and unexpected hook payloads.

A tool can rename a hook event or change its payload in a new version. Nothing fails then — the
hook just stops running or reads empty fields. This module keeps the evidence that shows it.

Responsibilities:
    - compare a tool's version with the versions its adapter was checked against
    - record each hook run per tool and event (`.lantern/hook-state/heartbeat.json`)
    - record hook calls whose payload lacks fields every call should have (`unexpected.jsonl`)
    - tell which hook events stopped running

Not here:
    - which versions a tool supports → each tool file (Tool.min_version · verified_version)
    - showing the results → check/doctor.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any

from ..core.project import Project
from .base import HookInput, Tool, hook_state_dir

HEARTBEAT = "heartbeat.json"
UNEXPECTED = "unexpected.jsonl"
KEEP_UNEXPECTED = 50  # the newest calls kept in unexpected.jsonl
EVERY_SESSION = frozenset({"session-start", "prompt", "stop"})  # events that fire in every session
MISSED_STARTS = 3  # an every-session event silent for this many session starts is reported
REQUIRED: dict[str, tuple[str, ...]] = {"post-tool": ("session", "tool")}  # HookInput fields each call must fill
DEFAULT_REQUIRED = ("session",)


def parse_version(text: str) -> tuple[int, ...] | None:
    """Find the first dotted version number in a text.

    Args:
        text: E.g. the output of `codex --version`.

    Returns:
        The numbers, or None when there is no version.

    Example:
        >>> parse_version("codex-cli 0.164.0"), parse_version("2.1.308 (Claude Code)"), parse_version("?")
        ((0, 164, 0), (2, 1, 308), None)
    """
    m = re.search(r"\d+(?:\.\d+)+", text)
    return tuple(int(x) for x in m.group(0).split(".")) if m else None


def version_verdict(tool: Tool, version: str) -> str:
    """Compare an installed version with the versions the tool's adapter knows.

    Args:
        tool: The tool adapter.
        version: The installed version, e.g. "2.1.308".

    Returns:
        "old" (below min_version), "new" (above verified_version), "ok", or "" when the version can't be read.

    Example:
        >>> from lanternspec.tools import get
        >>> [version_verdict(get("codex"), v) for v in ("0.164.0", "0.170.1", "x")]
        ['ok', 'new', '']
    """
    now = parse_version(version)
    if now is None:
        return ""
    low, high = parse_version(tool.min_version), parse_version(tool.verified_version)
    if low and now < low:
        return "old"
    if high and now > high:
        return "new"
    return "ok"


def installed_version(tool: Tool) -> str | None:
    """Ask the installed tool for its version (`<launch> --version`).

    Args:
        tool: The tool adapter.

    Returns:
        The version text, "" when the command runs but prints no version, None when the command is missing.

    Example:
        >>> installed_version(get("codex"))  # doctest: +SKIP
        '0.164.0'
    """
    if not shutil.which(tool.launch):
        return None
    try:
        r = subprocess.run([tool.launch, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    found = parse_version(r.stdout + r.stderr)
    return ".".join(map(str, found)) if found else ""


def missing_fields(event: str, inp: HookInput) -> list[str]:
    """List the fields a hook call should have filled but left empty.

    Args:
        event: Our hook event.
        inp: The call as the tool adapter read it.

    Returns:
        Field names, e.g. ["session"]; empty when the call looks as expected.

    Example:
        >>> missing_fields("post-tool", HookInput(session="s1")), missing_fields("stop", HookInput(session="s1"))
        (['tool'], [])
    """
    return [f for f in REQUIRED.get(event, DEFAULT_REQUIRED) if not getattr(inp, f)]


def record(project: Project, tool: Tool, event: str, inp: HookInput, data: dict[str, Any]) -> None:
    """Note one hook run, and the payload's keys when fields every call should have are empty.

    Only key names are kept, never values — a payload may carry the user's words. Errors are
    swallowed: a hook must never fail because of its own bookkeeping.

    Args:
        project: The project.
        tool: The tool that called.
        event: Our hook event.
        inp: The call as the tool adapter read it.
        data: The raw payload.

    Example:
        >>> record(project, get("claude"), "stop", HookInput(session="s1"), {"session_id": "s1"})  # doctest: +SKIP
    """
    try:
        folder = hook_state_dir(project)
        now = datetime.now().isoformat(timespec="seconds")
        beats = heartbeat(project)
        mine = beats.setdefault(tool.name, {"starts": 0, "events": {}})
        if event == "session-start":
            mine["starts"] += 1
        seen = mine["events"].setdefault(event, {"count": 0})
        seen.update(last=now, count=seen["count"] + 1, at_start=mine["starts"])
        (folder / HEARTBEAT).write_text(json.dumps(beats, ensure_ascii=False, indent=1), encoding="utf-8")
        missing = missing_fields(event, inp)
        if missing:
            line = {"at": now, "tool": tool.name, "event": event, "missing": missing, "keys": sorted(data)}
            path = folder / UNEXPECTED
            old = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
            kept = [*old, json.dumps(line, ensure_ascii=False)][-KEEP_UNEXPECTED:]
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError):
        pass


def heartbeat(project: Project) -> dict[str, Any]:
    """Read the hook-run record.

    Args:
        project: The project.

    Returns:
        Tool name → {"starts": session starts, "events": event → {"count", "last", "at_start"}}; {} when none.

    Example:
        >>> heartbeat(project)["claude"]["events"]["stop"]["count"]  # doctest: +SKIP
        12
    """
    path = project.state / "hook-state" / HEARTBEAT
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def unexpected(project: Project) -> list[dict[str, Any]]:
    """Read the recorded hook calls that lacked expected fields, oldest first.

    Args:
        project: The project.

    Returns:
        One dict per call: at · tool · event · missing · keys.

    Example:
        >>> unexpected(project)[-1]["missing"]  # doctest: +SKIP
        ['tool']
    """
    path = project.state / "hook-state" / UNEXPECTED
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def silent_events(tool: Tool, beats: dict[str, Any]) -> list[str]:
    """Find the every-session events of a tool that stopped running while sessions went on.

    Args:
        tool: The tool adapter (its hook_events say what we installed).
        beats: That tool's entry of the heartbeat record.

    Returns:
        Our event names that missed MISSED_STARTS session starts in a row, or never ran while
        other events did (session-start itself counts when the others ran MISSED_STARTS times).

    Example:
        >>> from lanternspec.tools import get
        >>> beats = {"starts": 5, "events": {"session-start": {"count": 5, "at_start": 5},
        ...          "prompt": {"count": 9, "at_start": 5}, "stop": {"count": 2, "at_start": 1}}}
        >>> silent_events(get("claude"), beats)
        ['stop']
    """
    starts = int(beats.get("starts") or 0)
    events = beats.get("events") or {}
    out = []
    for event in sorted(EVERY_SESSION & set(tool.hook_events())):
        seen = events.get(event)
        if event == "session-start":
            others = sum(int(v.get("count") or 0) for k, v in events.items() if k != event)
            if not seen and others >= MISSED_STARTS:
                out.append(event)
        elif starts - int((seen or {}).get("at_start") or 0) >= MISSED_STARTS:
            out.append(event)
    return out
