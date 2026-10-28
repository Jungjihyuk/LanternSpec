"""Work-line steps the skills record: work stage · design approval · unit-size log (`작업 단위 기록`).

Not here:
    - task-level progress (start · done) → work/tasks.py
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter, sections
from ..core.names import WORK_DOCS
from ..core.project import Project, read, today, write


def unit_log_add(project: Project, what: str, recommended: str, chosen: str, reason: str) -> Path:
    """Add one row to `작업 단위 기록.md`: the work unit the AI recommended and the one the person chose.

    The document is created from its template when missing.

    Args:
        project: The project.
        what: What was being split, e.g. "W-012 로그인".
        recommended: The AI's recommendation.
        chosen: What the person chose.
        reason: Why, in one line.

    Returns:
        The unit-size log document.

    Example:
        >>> unit_log_add(project, "W-012 로그인", "할 일 3개", "할 일 2개", "버튼은 하나로")  # doctest: +SKIP
        PosixPath('…/규칙 · 결정 기록/작업 단위 기록.md')
    """
    n = project.names
    p = project.folder("rules") / n.file("unit_log")
    if not p.exists():
        from .scaffold import create_from_template

        create_from_template(project, n.doc("unit_log"), p)
    if n.is_unused("unit_log"):
        return p
    row = f"| {today()} | {what} | {recommended} | {chosen} | {reason} |".replace("\n", " ")
    text = read(p)
    m = sections.find(text, n.titles("unit_log"))
    if m is None:
        raise sections.SectionMissing(n, "unit_log", p)
    parts = m.group(2).split("\n")
    last_row = max((i for i, l in enumerate(parts) if l.startswith("|")), default=None)
    parts.insert(0 if last_row is None else last_row + 1, row)
    text = text[: m.start(2)] + "\n".join(parts) + text[m.end(2) :]
    write(p, frontmatter.set_fields(text, {}))
    return p


def work_stage(project: Project, work_id: str, stage: str) -> list[Path]:
    """Set the stage of a work: the `status` of its 기획 · 설계 · 할 일 · 기록 documents.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        stage: A work_status value from enums.yaml, e.g. "설계".

    Returns:
        The documents that were changed.

    Raises:
        ValueError: The stage is not a work_status value, or the work does not exist.

    Example:
        >>> [p.name for p in work_stage(project, "W-012", "설계")]  # doctest: +SKIP
        ['기획.md', '설계.md']
    """
    enums = project.enums
    if stage not in enums.values("work_status"):
        raise ValueError(f"단계 '{stage}'는 작업 단계가 아닙니다 (가능: {', '.join(enums.values('work_status'))})")
    folder = project.find_work(work_id)
    if folder is None:
        raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
    changed = []
    for role in WORK_DOCS:
        p = project.doc_path(folder, role)
        if p.exists():
            write(p, frontmatter.set_fields(read(p), {"status": stage}))
            changed.append(p)
    return changed


def design_approve(project: Project, work_id: str, by: str) -> Path:
    """Record that a work's design was approved (`approved: <date> <who>` in `설계.md`).

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        by: Who approved; may be empty.

    Returns:
        The design document.

    Raises:
        ValueError: The work is not in progress or has no `설계.md`.

    Example:
        >>> design_approve(project, "W-012", "지혁").name  # doctest: +SKIP
        '설계.md'
    """
    folder = project.find_work(work_id, include_archive=False)
    p = project.doc_path(folder, "design") if folder else None
    if p is None or not p.exists():
        raise ValueError(f"{work_id}에 {project.names.file('design')}이 없습니다")
    value = f"{today()} {by}".strip()
    write(p, frontmatter.set_fields(read(p), {"approved": value}))
    return p
