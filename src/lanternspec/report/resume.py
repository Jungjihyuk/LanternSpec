"""`lantern resume` — sum up an earlier conversation so any AI tool can carry it on, even after it was cut off.

Responsibilities:
    - list the project's recent conversations (tool · time · cut off or not · last request)
    - show where the chosen one stopped: the last requests, the AI's last words, the files it changed,
      the uncommitted changes and the work in progress — the tail only, earlier parts with `--more`

Not here:
    - recording the conversations → tools/sessions.py
    - reading each tool's transcript → each tool file (Tool.read_transcript)
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.messages import msg
from ..core.project import Project, git, git_out

PAGE = 6  # messages shown per page of the transcript tail
REQUESTS, REQUEST_CHARS, ANSWER_CHARS = 3, 300, 600
RESUME_CALL = re.compile(r"(?:^|\s)[/$]l-resume\b")  # the conversation asking to resume is not the one to resume


def _short(text: str, limit: int) -> str:
    one = " ".join(text.split())
    return one if len(one) <= limit else one[: limit - 1] + "…"


def _when(iso: str) -> str:
    return iso[5:16].replace("T", " ") if len(iso) >= 16 else iso


def summary(project: Project, session: str | None = None, more: int = 0) -> list[str]:
    """Sum up the recent conversations and where one of them stopped.

    Args:
        project: The project.
        session: Which conversation: its number in the list or the start of its id; the newest when None.
        more: How many pages further back in the transcript to show (0 = the tail).

    Returns:
        Lines for the person and the AI.

    Example:
        >>> summary(project)[0]  # doctest: +SKIP
        '지난 대화 (이 프로젝트, 최근 2개)'
    """
    from ..tools import REGISTRY
    from ..tools.sessions import recent

    found = [s for s in recent(project) if not RESUME_CALL.search(s.last_prompt)]
    if not found:
        return [msg("No earlier conversations recorded — they are recorded from LanternSpec 0.2.2 on, in projects with its hooks")]
    out = [msg("Earlier conversations (this project, latest {count})", count=min(len(found), 5))]
    for i, s in enumerate(found[:5], start=1):
        state = msg("⚠ cut off") if s.cut_off else msg("finished")
        label = REGISTRY[s.tool].label if s.tool in REGISTRY else s.tool
        out.append(f' {i}. {label} · {_when(s.last_at)} · {state} · "{_short(s.last_prompt, 60)}"')
    chosen = found[0]
    if session:
        pick = [s for i, s in enumerate(found, start=1) if session == str(i) or s.id.startswith(session)]
        if not pick:
            return [*out, msg("No conversation '{session}' — pick a number from the list", session=session)]
        chosen = pick[0]
    out += ["", msg("→ Where conversation {id} stopped", id=chosen.id[:8])]
    out += _tail(chosen.tool, chosen.transcript, more)
    out += _work_state(project)
    out += [
        "",
        msg("(earlier messages: lantern resume --more {next} · another conversation: lantern resume --session <number>)", next=more + 1),
    ]
    return out


def _tail(tool_name: str, transcript: str, more: int) -> list[str]:
    """The last requests, the AI's last words and the changed files of one page of a transcript."""
    from ..tools import REGISTRY

    path = Path(transcript) if transcript else None
    if path is None or not path.exists():
        return [msg("  The transcript is gone or was never named: {path}", path=transcript or "-")]
    turns = REGISTRY[tool_name].read_transcript(path) if tool_name in REGISTRY else None
    if turns is None:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
        return [msg("  Couldn't read this transcript format — its last lines as they are ({path}):", path=path)] + [
            f"    {_short(line, 200)}" for line in raw
        ]
    end = max(len(turns) - PAGE * more, 0)
    page = turns[max(end - PAGE, 0) : end]
    if not page:
        return [msg("  Nothing earlier in this conversation")]
    out = []
    asks = [t for t in page if t.role == "user" and t.text][-REQUESTS:]
    if asks:
        out.append(msg("  Requests:"))
        out += [f"    - {_short(t.text, REQUEST_CHARS)}" for t in asks]
    said = [t for t in page if t.role == "assistant" and t.text]
    if said:
        out.append(msg("  The AI's last words: {text}", text=_short(said[-1].text, ANSWER_CHARS)))
    files = list(dict.fromkeys(f for t in page for f in t.files))
    if files:
        out.append(msg("  Files it changed: {items}", items=", ".join(files[-10:])))
    last = page[-1]
    if last.role == "user":
        out.append(msg("  The last request got no answer — the conversation stopped right after it"))
    elif last.tools and not last.text:
        out.append(msg("  It was in the middle of: {items}", items=", ".join(dict.fromkeys(last.tools))))
    return out


def _work_state(project: Project) -> list[str]:
    """Uncommitted changes (code and documents) and the work in progress, to check the conversation against."""
    from .status import lines

    out = []
    roots = {project.root, project.docs_git_cwd()}
    changed = []
    for root in roots:
        if git(["rev-parse", "--git-dir"], root).returncode == 0:
            changed += [line[3:] for line in git_out(["-c", "core.quotepath=false", "status", "--porcelain"], root).splitlines() if line]
    if changed:
        out.append(
            msg(
                "  Uncommitted changes {count}: {items}",
                count=len(changed),
                items=", ".join(changed[:8]) + (" …" if len(changed) > 8 else ""),
            )
        )
    if project.profile.exists:
        out += [f"  {line}" for line in lines(project)]
    return out
