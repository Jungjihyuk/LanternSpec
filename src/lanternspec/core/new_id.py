"""Issue IDs: IDEA-001 · W-012 · W-012-T03 · ADR-004 · D-007 · MTG-001.

The next number is always max(existing)+1, found by scanning file names, frontmatter
and task lines — so the same project state always yields the same ID.

Responsibilities:
    - the next document ID of each kind (IDEA · W · ADR · D · MTG)
    - the next task ID inside a work

Not here:
    - creating the document that carries the ID → work/scaffold.py
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from . import frontmatter
from .messages import msg
from .project import Project, nfc, read

KINDS: dict[str, dict[str, object]] = {
    "idea": {"prefix": "IDEA", "width": 3, "folder": "ideas"},
    "work": {"prefix": "W", "width": 3, "folder": "works"},
    "adr": {"prefix": "ADR", "width": 3, "folder": "decisions"},
    "debt": {"prefix": "D", "width": 3, "folder": "debt_cards"},
    "meeting": {"prefix": "MTG", "width": 3, "folder": "meetings"},
}
ALIASES = {"ideas": "idea", "w": "work", "task": "task", "decision": "adr", "d": "debt", "mtg": "meeting"}
TASK_RE = re.compile(r"\b(W-\d{3,})-T(\d{2,})\b")
ID_RE = re.compile(r"\b(IDEA|W|ADR|D|MTG)-(\d{3,})\b")


def _numbers(prefix: str, texts: Iterable[str]) -> Iterable[int]:
    pat = re.compile(rf"(?<![A-Z0-9-]){re.escape(prefix)}-(\d{{3,}})(?!-T|\d)")
    for t in texts:
        for m in pat.finditer(t):
            yield int(m.group(1))


def next_id(project: Project, kind: str) -> str:
    """Return the next free ID of a kind.

    File names, `id` frontmatter fields and (for works) `work/W-…` branches all reserve numbers.

    Args:
        project: The project.
        kind: "idea", "work", "adr", "debt" or "meeting" (aliases such as "w", "d", "decision" work too).

    Returns:
        The ID, e.g. "W-013".

    Raises:
        ValueError: The kind is unknown.

    Example:
        >>> next_id(project, "debt")  # doctest: +SKIP
        'D-008'
    """
    kind = ALIASES.get(kind, kind)
    if kind not in KINDS:
        raise ValueError(msg("Unknown ID kind: {kind} (available: {items} · task W-012)", kind=kind, items=", ".join(KINDS)))
    spec = KINDS[kind]
    prefix = str(spec["prefix"])
    width = int(spec["width"])  # type: ignore[arg-type]
    texts = []
    if project.docs.exists():
        for p in project.docs.rglob("*"):
            texts.append(nfc(p.name))
            if p.is_file() and p.suffix == ".md":
                try:
                    meta = frontmatter.parse(read(p)).meta
                except (OSError, UnicodeDecodeError):
                    continue
                if meta.get("id"):
                    texts.append(str(meta["id"]))
    # worktree branches (work/W-012) also reserve work numbers
    if kind == "work":
        from .project import git_out

        texts += git_out(["branch", "--list", "work/*", "--format=%(refname:short)"], project.root).splitlines()
    n = max(_numbers(prefix, texts), default=0) + 1
    return f"{prefix}-{n:0{width}d}"


def next_task_id(project: Project, work_id: str, tasks_file: Path | None = None) -> str:
    """Return the next task ID of a work.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        tasks_file: The task list to read; the work's `할 일.md` when None.

    Returns:
        The task ID, e.g. "W-012-T03".

    Raises:
        ValueError: tasks_file is None and the work folder does not exist.

    Example:
        >>> next_task_id(project, "W-012")  # doctest: +SKIP
        'W-012-T03'
    """
    work_id = work_id.upper()
    if tasks_file is None:
        work = project.find_work(work_id)
        if work is None:
            raise ValueError(msg("Work folder {work_id} not found", work_id=work_id))
        tasks_file = project.doc_path(work, "tasks")
    n = 0
    if tasks_file.exists():
        for m in TASK_RE.finditer(read(tasks_file)):
            if m.group(1) == work_id:
                n = max(n, int(m.group(2)))
    return f"{work_id}-T{n + 1:02d}"
