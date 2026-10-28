"""Current status in three lines: work in progress · next task · open ❓ questions.

Shown at session start, by `lantern status` and at the top of reports.
"""

from __future__ import annotations

from ..core import frontmatter
from ..core.messages import msg
from ..core.project import Project, read, work_id_of, work_name_of
from ..core.taskfile import parse_tasks
from ..work.tasks import next_task


def open_unknowns(project: Project) -> list[tuple[str, int]]:
    """Count the open "❓ 확인 필요" marks in documents still in use (active works and current state).

    Writing guides and example lines that only mention the mark are not counted.

    Args:
        project: The project.

    Returns:
        (document path from the docs root, count) for each document with open marks.

    Example:
        >>> open_unknowns(project)  # doctest: +SKIP
        [('2. 작업/W-012 로그인/설계.md', 2)]
    """
    unknown = project.names.marker("unknown")
    out = []
    targets = []
    for w in project.work_dirs():
        targets += sorted(w.glob("*.md"))
    cur = project.folder("current")
    if cur.exists():
        targets += sorted(cur.rglob("*.md"))
    for p in targets:
        lines = [
            l
            for l in read(p).split("\n")
            if unknown in l and "[!guide]" not in l and f"`{unknown}" not in l and not l.lstrip().startswith("> -")
        ]
        if lines:
            out.append((project.docs_rel(p), len(lines)))
    return out


def lines(project: Project) -> list[str]:
    """Build the three status lines.

    Args:
        project: The project.

    Returns:
        [works in progress (up to three, with stage and task progress), next task, open ❓ marks].

    Example:
        >>> lines(project)  # doctest: +SKIP
        ['📦 진행 중: W-012 로그인 (구현, 할 일 1/3)', '▶ 다음 할 일: W-012-T02 버튼 [S]', '❓ 확인 필요: 없음']
    """
    works = project.work_dirs()
    if works:
        parts = []
        for w in works[:3]:
            plan = project.doc_path(w, "plan")
            meta = frontmatter.parse(read(plan)).meta if plan.exists() else {}
            stage = str(meta.get("status") or "")
            extra = ""
            tf = project.doc_path(w, "tasks")
            if tf.exists():
                ts = parse_tasks(read(tf), project.names)
                if ts:
                    extra = msg(", tasks {sum}/{count}", sum=sum(t.done for t in ts), count=len(ts))
            design = project.doc_path(w, "design")
            if (
                design.exists()
                and not frontmatter.parse(read(design)).meta.get("approved")
                and stage == project.enums.value("work_status", "design")
            ):
                extra += msg(", ⏳ design awaiting approval")
            parts.append(f"{work_id_of(w)} {work_name_of(w)} ({stage}{extra})")
        more = msg(" and {value} more", value=len(works) - 3) if len(works) > 3 else ""
        first = msg("📦 In progress: ") + " · ".join(parts) + more
    else:
        first = msg("📦 In progress: none — start with /l-idea or /l-plan")
    nxt = next_task(project) if works else None
    if nxt and nxt.task:
        second = msg("▶ Next task: {id} {title}", id=nxt.task.id, title=nxt.task.title) + (f" [{nxt.task.size}]" if nxt.task.size else "")
    elif nxt and nxt.all_done:
        second = msg("▶ Next task: all tasks done — update the current state (/l-build wrap-up)")
    elif nxt and nxt.skipped:
        tid, why = nxt.skipped[0]
        second = msg("▶ Next task: none can start now ({tid}: {why})", tid=tid, why=why)
    else:
        second = msg("▶ Next task: none")
    unknowns = open_unknowns(project)
    if unknowns:
        total = sum(n for _, n in unknowns)
        where = ", ".join(f"{d} ({n})" for d, n in unknowns[:3])
        third = msg("{marker} {total}: {where}", marker=project.names.marker("unknown"), total=total, where=where)
    else:
        third = msg("{marker}: none", marker=project.names.marker("unknown"))
    return [first, second, third]
