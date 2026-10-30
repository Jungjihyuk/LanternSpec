"""Which conversations happened in this project, in which AI tool, and where each tool keeps their transcript.

Every hook call updates one small record per conversation in `.lantern/sessions/` (git-ignored):
the tool, when it started, the transcript path the tool named, the last request and the last event.
A conversation whose last event is not a stop ended in the middle of a turn (cut off).

Responsibilities:
    - record each conversation from the hook calls (any tool)
    - list the conversations, newest first

Not here:
    - reading a transcript → each tool file (Tool.read_transcript)
    - summing a conversation up to carry it on → report/resume.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..core.project import Project
from ..core.state import ensure_state_dir
from .base import HookInput, Tool

FOLDER = "sessions"
PROMPT_KEEP = 200  # characters of the last request kept in the record


@dataclass
class Session:
    """One conversation as the hooks saw it.

    Attributes:
        id: The tool's conversation id.
        tool: The tool name, e.g. "codex".
        started: When the first hook call came (ISO time).
        last_at: When the last hook call came.
        last_event: Our event of the last hook call, e.g. "stop".
        last_prompt: The last request the user wrote (shortened).
        transcript: The transcript file the tool named ("" when it never did).

    Example:
        >>> Session("s1", "claude", "2026-10-30T10:00:00", "2026-10-30T10:05:00", "prompt").cut_off
        True
    """

    id: str
    tool: str
    started: str
    last_at: str
    last_event: str
    last_prompt: str = ""
    transcript: str = ""

    @property
    def cut_off(self) -> bool:
        """Whether the conversation stopped in the middle of a turn (no stop after the last call)."""
        return self.last_event != "stop"


def _path(project: Project, session: str) -> Path:
    return project.state / FOLDER / (re.sub(r"[^\w.-]", "_", session)[:80] + ".json")


def record(project: Project, tool: Tool, event: str, inp: HookInput) -> None:
    """Update the conversation's record from one hook call. Errors are swallowed: a hook never fails on bookkeeping.

    Args:
        project: The project.
        tool: The tool that called.
        event: Our hook event.
        inp: The call as the tool adapter read it.

    Example:
        >>> record(project, get("codex"), "prompt", HookInput(session="s1", prompt="$l-build W-012"))  # doctest: +SKIP
    """
    if not inp.session:
        return
    try:
        path = _path(project, inp.session)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        now = datetime.now().isoformat(timespec="seconds")
        data.update(id=inp.session, tool=tool.name, last_at=now, last_event=event)
        data.setdefault("started", now)
        if inp.transcript:
            data["transcript"] = inp.transcript
        if event == "prompt" and inp.turn_start and inp.prompt.strip():
            data["last_prompt"] = " ".join(inp.prompt.split())[:PROMPT_KEEP]
        if not path.parent.exists():
            ensure_state_dir(project)  # an older .gitignore learns to leave this folder out
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass


def recent(project: Project, limit: int = 10) -> list[Session]:
    """List the recorded conversations, newest first.

    Args:
        project: The project.
        limit: How many to return.

    Returns:
        The conversations, by their last hook call.

    Example:
        >>> [s.tool for s in recent(project, 2)]  # doctest: +SKIP
        ['codex', 'claude']
    """
    folder = project.state / FOLDER
    out = []
    for path in folder.glob("*.json") if folder.exists() else []:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            out.append(
                Session(
                    str(d["id"]),
                    str(d.get("tool") or ""),
                    str(d.get("started") or ""),
                    str(d.get("last_at") or ""),
                    str(d.get("last_event") or ""),
                    str(d.get("last_prompt") or ""),
                    str(d.get("transcript") or ""),
                )
            )
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda s: s.last_at, reverse=True)[:limit]
