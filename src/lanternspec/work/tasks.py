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
from ..core.project import Project, now_minute, read, work_id_of, write
from ..core.taskfile import Task, TaskGraph, find_task, parse_criteria, parse_tasks, set_attr, set_checked
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
        raise ValueError(f"진행 중인 작업 {work_id}를 찾지 못했습니다")
    p = folder / "할 일.md"
    if not p.exists():
        raise ValueError(f"{work_id}에 할 일.md가 없습니다 — /l-task 먼저")
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
            raise ValueError(f"진행 중인 작업 {work_id}를 찾지 못했습니다")
        tf = w / "할 일.md"
        if not tf.exists():
            continue
        graph = TaskGraph(parse_tasks(read(tf)))
        any_tasks = any_tasks or bool(graph.tasks)
        for t in graph.tasks:
            if t.done:
                continue
            reason = graph.blocked_reason(t)
            if reason is None and ui_required and t.screen and not has_mockup(w):
                reason = "화면 시안 없음 — 화면/ 아래 이미지 · HTML 필요"
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
    tasks = parse_tasks("\n".join(lines))
    t = find_task(tasks, task_id)
    if t is None:
        raise ValueError(f"할 일 {task_id}가 {project.rel(tf)}에 없습니다")
    lines[t.line_no] = edit(lines[t.line_no], t)
    text = frontmatter.set_fields("\n".join(lines), {})
    write(tf, text)
    new_tasks = parse_tasks(text)
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
        return line if t.started else set_attr(line, "시작", now_minute())

    t, tf, _ = _edit_task(project, task_id, edit)
    for doc in ("기획.md", "할 일.md", "기록.md"):
        _bump_stage(project, tf.parent / doc, "build")
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
            line = set_attr(line, "시작", now_minute())
        return set_attr(line, "완료", now_minute())

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
        import re

        line = set_checked(line, False)
        return re.sub(r"\s*\[완료::[^\]]*\]", "", line)

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
        raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
    plan = folder / "기획.md"
    lines = read(plan).split("\n")
    for c in parse_criteria("\n".join(lines)):
        if c.id == ac_id.upper():
            lines[c.line_no] = set_checked(lines[c.line_no], True)
            write(plan, frontmatter.set_fields("\n".join(lines), {}))
            return plan
    raise ValueError(f"{work_id} 기획.md에 {ac_id}가 없습니다")


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
        tf = w / "할 일.md"
        if not tf.exists():
            out.append(f"{work_id_of(w)}: 할 일 없음")
            continue
        tasks = parse_tasks(read(tf))
        graph = TaskGraph(tasks)
        out.append(f"{work_id_of(w)}: {sum(t.done for t in tasks)}/{len(tasks)} 완료")
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
        raise ValueError("크기는 S · M · L 중 하나입니다")
    wid = work_id.upper()
    tf = _tasks_file(project, wid)
    # the scaffolded example line (`… {{할 일 (필수)}} …`) gives way to the first real task
    lines = [l for l in read(tf).split("\n") if not (re.match(r"^\s*- \[ \] W-\d{3,}-T\d{2,}\b", l) and "{{할 일" in l)]
    existing = parse_tasks("\n".join(lines))
    n = max((int(t.id.rsplit("-T", 1)[1]) for t in existing if t.work_id == wid), default=0)
    task_id = f"{wid}-T{n + 1:02d}"
    parts = [f"- [ ] {task_id}" + (" [P]" if parallel else "") + f" {what.strip()}", f"[크기:: {size}]"]
    if ac:
        parts.append(f"[기준:: {', '.join(a.upper() for a in ac)}]")
    if after:
        parts.append(f"[먼저:: {', '.join(a.upper().rsplit('-', 1)[-1] for a in after)}]")
    for key, value in (("담당", owner), ("화면", screen), ("시작 예정", start_plan), ("마감 예정", due_plan)):
        if value:
            parts.append(f"[{key}:: {value}]")
    line = " ".join(parts) + (" ❓ 확인 필요" if unknown else "")
    if existing:
        insert_at = existing[-1].line_no + 1
    else:  # first task: right under "## 할 일"
        insert_at = next((i + 1 for i, l in enumerate(lines) if l.strip() == "## 할 일"), len(lines))
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
        if insert_at < len(lines) and lines[insert_at].startswith(("<!--", "## ")):
            lines.insert(insert_at, "")
    lines.insert(insert_at, line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip("\n") + "\n"
    write(tf, frontmatter.set_fields(text, {}))
    return find_task(parse_tasks(read(tf)), task_id)  # type: ignore[return-value]


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
        if w is None or not (w / "할 일.md").exists():
            continue
        graph = TaskGraph(parse_tasks(read(w / "할 일.md")))
        for t in graph.tasks:
            if t.done or graph.blocked_reason(t):
                continue
            if ui_required and t.screen and not has_mockup(w):
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
    tasks = parse_tasks("\n".join(lines))
    day = dt.date.fromisoformat(start) if start else dt.date.today()
    used = 0.0
    out = [
        "크기별 기준 시간: "
        + " · ".join(
            f"{k} {v:.1f}시간" + (f" (실제 {len(hist[k])}개 중간값)" if len(hist.get(k, [])) >= 2 else " (기본값)")
            for k, v in per_size.items()
        )
        + f" · 하루 {hours_per_day:g}시간"
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
            lines[t.line_no] = set_attr(set_attr(lines[t.line_no], "시작 예정", begin.isoformat()), "마감 예정", end.isoformat())
    if apply:
        write(tf, frontmatter.set_fields("\n".join(lines), {}))
        out.append("✔ 할 일.md에 [시작 예정] · [마감 예정]을 적었습니다")
    else:
        out.append("제안입니다 — 사람이 동의하면 --apply")
    return out
