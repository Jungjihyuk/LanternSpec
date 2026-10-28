"""`lantern task next|start|done|list` — used inside /l-build. Not a user command.

Responsibilities:
    - choose the next task that can start (dependencies, ❓ marks, missing mockups)
    - add tasks with the next ID; mark start, done and reopen with times
    - tick acceptance criteria once verified; suggest due dates from past durations

Not here:
    - reading and editing task lines → core/taskfile.py
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core import frontmatter
from ..core.messages import msg
from ..core.project import Project, now_minute, read, work_id_of, write
from ..core.taskfile import Task, TaskGraph, drop_attr, find_task, parse_criteria, parse_tasks, set_attr, set_checked
from .epic_rules import has_mockup

STAGE_ROLES = ["plan", "design", "tasks", "build", "done"]  # work_status roles, in order


@dataclass
class NextResult:
    """What `lantern task next` found.

    Attributes:
        task: The next task to start; None when nothing can start.
        work: The work folder of that task.
        skipped: (task ID, reason) for each unfinished task that cannot start yet.
        all_done: Whether there were tasks and every one is done.

    Example:
        >>> NextResult(task=None, work=None).all_done
        False
    """

    task: Task | None
    work: Path | None
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (task id, reason)
    all_done: bool = False


def _tasks_file(project: Project, work_id: str) -> Path:
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    p = project.doc_path(folder, "tasks")
    if not p.exists():
        raise ValueError(msg("{work_id} has no {name} — run /l-task first", work_id=work_id, name=p.name))
    return p


def _work_of_task(task_id: str) -> str:
    return task_id.upper().rsplit("-T", 1)[0]


def next_task(project: Project, work_id: str | None = None) -> NextResult:
    """Find the next task that can start, in work and file order.

    A task is skipped while it is done, marked ❓, waits on another task, or (under
    `plan.ui_reference: required`) builds a screen whose mockup is missing.

    Args:
        project: The project.
        work_id: Look only in this work; every work in progress when None.

    Returns:
        The next task, or the skipped tasks with their reasons.

    Raises:
        ValueError: work_id is given but the work is not in progress.

    Example:
        >>> next_task(project, "W-012").task.id  # doctest: +SKIP
        'W-012-T02'
    """
    works = [project.find_work(work_id, include_archive=False)] if work_id else project.work_dirs()
    ui_required = project.profile.get("plan.ui_reference") == "required"
    skipped: list[tuple[str, str]] = []
    any_tasks = False
    for w in works:
        if w is None:
            raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
        tf = project.doc_path(w, "tasks")
        if not tf.exists():
            continue
        graph = TaskGraph(parse_tasks(read(tf), project.names))
        any_tasks = any_tasks or bool(graph.tasks)
        for t in graph.tasks:
            if t.done:
                continue
            reason = graph.blocked_reason(t)
            if reason is None and ui_required and t.screen and not has_mockup(w, project.names):
                reason = msg("No screen mockup — needs an image · HTML under the screens folder")
            if reason:
                skipped.append((t.id, reason))
                continue
            return NextResult(task=t, work=w, skipped=skipped)
    all_done = any_tasks and not skipped
    return NextResult(task=None, work=None, skipped=skipped, all_done=all_done)


def _bump_stage(project: Project, path: Path, role: str) -> None:
    """Move a work doc forward to the stage with this role (never backward)."""
    if not path.exists():
        return
    order = [project.enums.value("work_status", r) for r in STAGE_ROLES]
    stage = project.enums.value("work_status", role)
    text = read(path)
    cur = str(frontmatter.parse(text).meta.get("status") or "")
    if cur in order and order.index(cur) >= order.index(stage):
        return
    write(path, frontmatter.set_fields(text, {"status": stage}))


def _edit_task(project: Project, task_id: str, edit: Callable[[str, Task], str]) -> tuple[Task, Path, list[Task]]:
    tf = _tasks_file(project, _work_of_task(task_id))
    lines = read(tf).split("\n")
    tasks = parse_tasks("\n".join(lines), project.names)
    t = find_task(tasks, task_id)
    if t is None:
        raise ValueError(msg("Task {task_id} is not in {rel}", task_id=task_id, rel=project.rel(tf)))
    lines[t.line_no] = edit(lines[t.line_no], t)
    text = frontmatter.set_fields("\n".join(lines), {})
    write(tf, text)
    new_tasks = parse_tasks(text, project.names)
    return find_task(new_tasks, task_id), tf, new_tasks  # type: ignore[return-value]


def start(project: Project, task_id: str) -> Task:
    """Mark a task started (`[시작:: time]`) and move the work's documents to the build stage.

    Args:
        project: The project.
        task_id: The task, e.g. "W-012-T02".

    Returns:
        The task as it is now.

    Raises:
        ValueError: The work or the task does not exist.

    Example:
        >>> start(project, "W-012-T02").started  # doctest: +SKIP
        '2026-10-28 09:00'
    """

    def edit(line: str, t: Task) -> str:
        return line if t.started else set_attr(line, "start", now_minute(), project.names)

    t, tf, _ = _edit_task(project, task_id, edit)
    for role in ("plan", "tasks", "record"):
        _bump_stage(project, project.doc_path(tf.parent, role), "build")
    return t


@dataclass
class DoneResult:
    """What `lantern task done` changed.

    Attributes:
        task: The task as it is now.
        checkpoints: Acceptance criteria whose tasks are now all done — check these now.
        work_done: Whether every task of the work is done.

    Example:
        >>> DoneResult(task=None, checkpoints=["AC-1"], work_done=False).checkpoints  # doctest: +SKIP
        ['AC-1']
    """

    task: Task
    checkpoints: list[str]  # AC ids whose tasks are now all done
    work_done: bool


def done(project: Project, task_id: str) -> DoneResult:
    """Check a task and stamp its finish time (and its start time if it was never started).

    Args:
        project: The project.
        task_id: The task, e.g. "W-012-T02".

    Returns:
        The task, the acceptance criteria now ready to check, and whether the work is done.

    Raises:
        ValueError: The work or the task does not exist.

    Example:
        >>> done(project, "W-012-T02").checkpoints  # doctest: +SKIP
        ['AC-1']
    """

    def edit(line: str, t: Task) -> str:
        line = set_checked(line, True)
        if not t.started:
            line = set_attr(line, "start", now_minute(), project.names)
        return set_attr(line, "finish", now_minute(), project.names)

    t, tf, tasks = _edit_task(project, task_id, edit)
    checkpoints = []
    for ac in t.criteria:
        linked = [x for x in tasks if ac in x.criteria]
        if linked and all(x.done for x in linked):
            checkpoints.append(ac)
    return DoneResult(task=t, checkpoints=checkpoints, work_done=all(x.done for x in tasks))


def reopen(project: Project, task_id: str) -> Task:
    """Uncheck a task and drop its finish time.

    Args:
        project: The project.
        task_id: The task, e.g. "W-012-T02".

    Returns:
        The task as it is now.

    Raises:
        ValueError: The work or the task does not exist.

    Example:
        >>> reopen(project, "W-012-T02").done  # doctest: +SKIP
        False
    """

    def edit(line: str, t: Task) -> str:
        return drop_attr(set_checked(line, False), "finish", project.names)

    t, _, _ = _edit_task(project, task_id, edit)
    return t


def check_ac(project: Project, work_id: str, ac_id: str) -> Path:
    """Tick an acceptance criterion in `기획.md` once it was verified.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        ac_id: The criterion, e.g. "AC-1".

    Returns:
        The plan document.

    Raises:
        ValueError: The work or the criterion does not exist.

    Example:
        >>> check_ac(project, "W-012", "AC-1").name  # doctest: +SKIP
        '기획.md'
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work {work_id} not found", work_id=work_id))
    plan = project.doc_path(folder, "plan")
    lines = read(plan).split("\n")
    for c in parse_criteria("\n".join(lines)):
        if c.id == ac_id.upper():
            lines[c.line_no] = set_checked(lines[c.line_no], True)
            write(plan, frontmatter.set_fields("\n".join(lines), {}))
            return plan
    raise ValueError(msg("{work_id} {name} has no {ac_id}", work_id=work_id, name=plan.name, ac_id=ac_id))


def summary(project: Project, work_id: str | None = None) -> list[str]:
    """List the tasks of works with their progress, for `lantern task list`.

    Args:
        project: The project.
        work_id: Only this work; every work in progress when None.

    Returns:
        Lines: one header per work, then one line per task (`[x]` done, `[▶]` started) with why it is blocked.

    Example:
        >>> summary(project, "W-012")[0]  # doctest: +SKIP
        'W-012: 1/3 완료'
    """
    out = []
    works = [project.find_work(work_id)] if work_id else project.work_dirs()
    for w in works:
        if w is None:
            continue
        tf = project.doc_path(w, "tasks")
        if not tf.exists():
            out.append(msg("{work_id_of}: no tasks", work_id_of=work_id_of(w)))
            continue
        tasks = parse_tasks(read(tf), project.names)
        graph = TaskGraph(tasks)
        out.append(msg("{work_id_of}: {sum}/{count} done", work_id_of=work_id_of(w), sum=sum(t.done for t in tasks), count=len(tasks)))
        for t in tasks:
            mark = "x" if t.done else ("▶" if t.started else " ")
            reason = "" if t.done else (graph.blocked_reason(t) or "")
            out.append(f"  [{mark}] {t.id} {t.title} [{t.size}]" + (f" — {reason}" if reason else ""))
    return out


def add(
    project: Project,
    work_id: str,
    what: str,
    size: str = "M",
    ac: list[str] | None = None,
    after: list[str] | None = None,
    owner: str = "",
    screen: str = "",
    start_plan: str = "",
    due_plan: str = "",
    unknown: bool = False,
    parallel: bool = False,
) -> Task:
    """Append a task line with the next ID. Replaces the template's example line.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        what: What to do, in one line.
        size: "S", "M" or "L".
        ac: Acceptance criteria the task serves, e.g. ["AC-1"].
        after: Tasks that must finish first, e.g. ["T01"].
        owner: Who does it (team projects).
        screen: The screen the task builds (matched with mockups).
        start_plan: Planned start date.
        due_plan: Planned due date.
        unknown: Mark the line "❓ 확인 필요" — it cannot start until checked.
        parallel: Mark the line `[P]` — it can run alongside other `[P]` tasks.

    Returns:
        The new task.

    Raises:
        ValueError: The size is not S · M · L, or the work or its `할 일.md` does not exist.

    Example:
        >>> add(project, "W-012", "카카오 버튼", size="S", ac=["AC-1"]).id  # doctest: +SKIP
        'W-012-T03'
    """
    import re

    if size not in ("S", "M", "L"):
        raise ValueError(msg("Size is one of S · M · L"))
    wid = work_id.upper()
    tf = _tasks_file(project, wid)
    n = project.names
    # the scaffolded example line (a task line with {{blanks}}) gives way to the first real task, in the same place
    lines = read(tf).split("\n")
    example = next((i for i, l in enumerate(lines) if re.match(r"^\s*- \[ \] W-\d{3,}-T\d{2,}\b", l) and "{{" in l), None)
    if example is not None:
        del lines[example]
    existing = parse_tasks("\n".join(lines), n)
    num = max((int(t.id.rsplit("-T", 1)[1]) for t in existing if t.work_id == wid), default=0)
    task_id = f"{wid}-T{num + 1:02d}"
    parts = [f"- [ ] {task_id}" + (" [P]" if parallel else "") + f" {what.strip()}", f"[{n.attr('size')}:: {size}]"]
    if ac:
        parts.append(f"[{n.attr('criteria')}:: {', '.join(a.upper() for a in ac)}]")
    if after:
        parts.append(f"[{n.attr('after')}:: {', '.join(a.upper().rsplit('-', 1)[-1] for a in after)}]")
    for role, value in (("owner", owner), ("screen", screen), ("start_plan", start_plan), ("due_plan", due_plan)):
        if value:
            parts.append(f"[{n.attr(role)}:: {value}]")
    line = " ".join(parts) + (f" {n.marker('unknown')}" if unknown else "")
    if existing:
        insert_at = existing[-1].line_no + 1
    elif example is not None:
        insert_at = example
    else:  # no task and no example line: add at the end
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("")
        insert_at = len(lines)
    lines.insert(insert_at, line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip("\n") + "\n"
    write(tf, frontmatter.set_fields(text, {}))
    return find_task(parse_tasks(read(tf), n), task_id)  # type: ignore[return-value]


def ready(project: Project, work_id: str | None = None) -> list[Task]:
    """List every task that can start now — `[P]` ones can go to parallel agents together.

    Args:
        project: The project.
        work_id: Only this work; every work in progress when None.

    Returns:
        The tasks that are not done and not blocked.

    Example:
        >>> [t.id for t in ready(project, "W-012")]  # doctest: +SKIP
        ['W-012-T02', 'W-012-T03']
    """
    out: list[Task] = []
    works = [project.find_work(work_id, include_archive=False)] if work_id else project.work_dirs()
    ui_required = project.profile.get("plan.ui_reference") == "required"
    for w in works:
        if w is None or not project.doc_path(w, "tasks").exists():
            continue
        graph = TaskGraph(parse_tasks(read(project.doc_path(w, "tasks")), project.names))
        for t in graph.tasks:
            if t.done or graph.blocked_reason(t):
                continue
            if ui_required and t.screen and not has_mockup(w, project.names):
                continue
            out.append(t)
    return out


DEFAULT_HOURS = {"S": 2.0, "M": 4.0, "L": 8.0}  # S an hour or two · M half a day · L a day (/l-task)


def estimate(project: Project, work_id: str, start: str | None = None, hours_per_day: float = 6.0, apply: bool = False) -> list[str]:
    """**Suggest** due dates from the actual median duration per size; writes only with apply.

    Sizes with fewer than two finished tasks use the defaults (S 2h · M 4h · L 8h). Weekends are skipped.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        start: First day (ISO date); today when None.
        hours_per_day: Working hours per day.
        apply: Write `[시작 예정]` · `[마감 예정]` into `할 일.md` (after the person agrees).

    Returns:
        Lines: the hours per size, one line per unfinished task, then what to do next.

    Raises:
        ValueError: The work or its `할 일.md` does not exist.

    Example:
        >>> estimate(project, "W-012", start="2026-10-28")[1]  # doctest: +SKIP
        'W-012-T02 카카오 버튼 [S] → 2026-10-28 ~ 2026-10-28'
    """
    import datetime as dt
    from statistics import median

    from ..report.evaluate import task_durations

    hist = task_durations(project)
    per_size = {k: (median(hist[k]) if len(hist.get(k, [])) >= 2 else DEFAULT_HOURS[k]) for k in DEFAULT_HOURS}
    tf = _tasks_file(project, work_id)
    lines = read(tf).split("\n")
    tasks = parse_tasks("\n".join(lines), project.names)
    day = dt.date.fromisoformat(start) if start else dt.date.today()
    used = 0.0
    out = [
        msg("Base hours by size: ")
        + " · ".join(
            msg("{k} {v:.1f}h", k=k, v=v)
            + (msg(" (median of {count} actual)", count=len(hist[k])) if len(hist.get(k, [])) >= 2 else msg(" (default)"))
            for k, v in per_size.items()
        )
        + msg(" · {hours_per_day:g} hours a day", hours_per_day=hours_per_day)
    ]
    for t in tasks:
        if t.done:
            continue
        need = per_size.get(t.size, DEFAULT_HOURS["M"])
        begin = day
        used += need
        while used > hours_per_day:
            used -= hours_per_day
            day += dt.timedelta(days=1)
            while day.weekday() >= 5:
                day += dt.timedelta(days=1)
        end = day
        out.append(f"{t.id} {t.title} [{t.size or '?'}] → {begin.isoformat()} ~ {end.isoformat()}")
        if apply:
            line = set_attr(lines[t.line_no], "start_plan", begin.isoformat(), project.names)
            lines[t.line_no] = set_attr(line, "due_plan", end.isoformat(), project.names)
    if apply:
        write(tf, frontmatter.set_fields("\n".join(lines), {}))
        n = project.names
        out.append(msg("✔ Wrote [{attr}] · [{attr2}] in {name}", name=tf.name, attr=n.attr("start_plan"), attr2=n.attr("due_plan")))
    else:
        out.append(msg("This is a suggestion — if the person agrees, --apply"))
    return out
