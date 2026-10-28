"""Save progress into a document's "지금 상황" section just before the conversation is compacted.

Responsibilities:
    - overwrite "지금 상황" of each active work's `기록.md` with the current state (progress · next · blocked · open questions)
    - move what it replaced into "지난 기록" so nothing is lost
    - without any `기록.md`, write to `4. 운영 기록/세션/<date>.md`
    - read "지금 상황" back so it can be put back after compaction

"지금 상황" and "지난 기록" are protected sections: they are found under any title the project gave them,
and a document without them is skipped (nothing is added; `lantern check` asks the person).

Not here:
    - deciding when to save → tools/agent_hooks.py (pre-compact · session-start)
    - finding a section by its titles → core/sections.py
    - picking the next task → work/tasks.py (next_task)
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter, sections
from ..core.messages import msg
from ..core.names import Names
from ..core.project import Project, now_minute, read, today, work_id_of, write
from ..core.taskfile import parse_tasks
from .scaffold import create_from_template
from .tasks import next_task


def append_history(text: str, stamp: str, old: str, titles: list[str]) -> str | None:
    r"""Append replaced "지금 상황" content, with a timestamp, to the end of "지난 기록".

    Args:
        text: The whole document.
        stamp: Timestamp, e.g. "2026-10-27 14:05".
        old: The replaced content.
        titles: Accepted titles of "지난 기록".

    Returns:
        The document with one more entry; None when it has no "지난 기록" section.

    Example:
        >>> print(append_history("## 지난 기록\n> [!guide] 쌓는다\n", "2026-10-27 14:05", "- 진행: A", ["지난 기록"]), end="")
        ## 지난 기록
        > [!guide] 쌓는다
        <BLANKLINE>
        - 2026-10-27 14:05
          - 진행: A
    """
    entry = f"- {stamp}\n" + "\n".join(f"  {l}" for l in old.split("\n") if l.strip()) + "\n"
    m = sections.find(text, titles)
    if m is None:
        return None
    body = m.group(2).rstrip("\n")
    return text[: m.start(2)] + body + "\n\n" + entry + ("\n" if text[m.end(2) :] else "") + text[m.end(2) :]


def work_state(project: Project, work: Path) -> str:
    """Describe one work item's current state in "지금 상황" form (3–4 lines).

    Args:
        project: The project.
        work: The work folder.

    Returns:
        `- 진행:` · `- 다음:` lines, plus `- 막힌 것:` · `- 열린 질문:` when there are any.

    Example:
        >>> print(work_state(project, work))  # doctest: +SKIP
        - 진행: 구현 · 할 일 1/3 · 하는 중 W-001-T02
        - 다음: W-001-T03 저장 버튼
    """
    wid = work_id_of(work)
    plan, tasks_file = project.doc_path(work, "plan"), project.doc_path(work, "tasks")
    stage = str(frontmatter.parse(read(plan)).meta.get("status") or "") if plan.exists() else ""
    tasks = parse_tasks(read(tasks_file), project.names) if tasks_file.exists() else []
    doing = [t.id for t in tasks if not t.done and t.started]
    progress = [stage] if stage else []
    if tasks:
        progress.append(msg("tasks {sum}/{count}", sum=sum(t.done for t in tasks), count=len(tasks)))
    if doing:
        progress.append(msg("doing ") + ", ".join(doing))
    summary = " · ".join(progress) or msg("not started")
    lines = [msg("- Progress: {summary}", summary=summary)]
    nxt = next_task(project, wid)
    if nxt.task:
        lines.append(msg("- Next: {id} {title}", id=nxt.task.id, title=nxt.task.title) + (msg(" (doing)") if nxt.task.id in doing else ""))
    elif nxt.all_done:
        lines.append(msg("- Next: all tasks done — update the current state"))
    else:
        lines.append(msg("- Next: no task set"))
    if nxt.skipped:
        lines.append(msg("- Blocked: ") + " · ".join(f"{tid} ({why})" for tid, why in nxt.skipped[:3]))
    from ..report.status import open_unknowns  # mentions inside guide text don't count

    folder = project.docs_rel(work)
    unknowns = sum(n for doc, n in open_unknowns(project) if doc.startswith(folder + "/"))
    if unknowns:
        lines.append(msg("- Open questions: {marker} {unknowns}", marker=project.names.marker("unknown"), unknowns=unknowns))
    return "\n".join(lines)


def save_before_compact(project: Project) -> dict[Path, str]:
    """Save progress into documents and return each document's previous "지금 상황".

    Overwrites "지금 상황" of every active work item that has a `기록.md`. Without any, the state of
    all active work goes to `4. 운영 기록/세션/<date>.md` (one per day).
    Previous content moves to "지난 기록". A document is skipped when it has no "지금 상황", when
    the project turned that section off, or when old content has nowhere to go (no "지난 기록").

    Args:
        project: The project.

    Returns:
        Saved document path → the "지금 상황" it held before (empty when it was empty or only blanks).
        Skipped documents are not included.
        This earlier context (written by a person or the AI) can be put back after compaction too.

    Example:
        >>> {project.rel(p): old for p, old in save_before_compact(project).items()}  # doctest: +SKIP
        {'docs/2. 작업/W-001 로그인/기록.md': '- 진행: 로그인 버튼 붙이는 중'}
    """
    names = project.names
    if names.is_unused("now"):
        return {}
    stamp = now_minute()
    records = [project.doc_path(w, "record") for w in project.work_dirs() if project.doc_path(w, "record").exists()]
    if records:
        saved = {rec: _overwrite_now(rec, work_state(project, rec.parent), stamp, names) for rec in records}
    else:
        session = project.folder("sessions") / f"{today()}.md"
        if not session.exists():
            create_from_template(project, names.doc("session"), session, {"id": f"SESSION-{today()}"})
        states = [f"**{work_id_of(w)}**\n{work_state(project, w)}" for w in project.work_dirs()]
        saved = {session: _overwrite_now(session, "\n\n".join(states) or msg("- No work in progress"), stamp, names)}
    return {path: old for path, old in saved.items() if old is not None}


def _overwrite_now(path: Path, body: str, stamp: str, names: Names) -> str | None:
    """Overwrite one document's "지금 상황", move meaningful old content to "지난 기록"; None when skipped."""
    text = read(path)
    replaced = sections.replace(text, names.titles("now"), body)
    if replaced is None:
        return None
    text, old = replaced
    old = "\n".join(l for l in old.split("\n") if l.strip() and "{{" not in l)  # drop unfilled {{blank}} lines
    meaningful = bool(old) and old.strip() != body.strip()
    if meaningful:
        kept = None if names.is_unused("past") else append_history(text, stamp, old, names.titles("past"))
        if kept is None:
            return None  # the old content has nowhere to go: leave the document as it is
        text = kept
    write(path, frontmatter.set_fields(text, {}))
    return old if meaningful else ""
