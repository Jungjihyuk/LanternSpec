"""Work-line steps the skills record: work stage · design approval · understanding mark · unit-size log (`작업 단위 기록`).

Not here:
    - task-level progress (start · done) → work/tasks.py
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter, sections
from ..core.messages import msg
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
        raise ValueError(
            msg("'{stage}' is not a work stage (available: {items})", stage=stage, items=", ".join(enums.values("work_status")))
        )
    folder = project.find_work(work_id)
    if folder is None:
        raise ValueError(msg("Work {work_id} not found", work_id=work_id))
    changed = []
    for role in WORK_DOCS:
        p = project.doc_path(folder, role)
        if p.exists():
            write(p, frontmatter.set_fields(read(p), {"status": stage}))
            changed.append(p)
    return changed


UNDERSTOOD = "understood"  # frontmatter key of the understanding mark; its values are yes · no
YES, NO = "yes", "no"


def design_approve(project: Project, work_id: str, by: str, understood: bool | None = None) -> Path:
    """Record that a work's design was approved (`approved: <date> <who>` in `설계.md`), and whether the person followed it.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        by: Who approved; may be empty.
        understood: True for "approved and understood", False for "approved, handed over"; None when it was not asked
            (a small design that passed on its own).

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
        raise ValueError(msg("{work_id} has no {file}", work_id=work_id, file=project.names.file("design")))
    value = f"{today()} {by}".strip()
    updates = {"approved": value} if understood is None else {"approved": value, UNDERSTOOD: YES if understood else NO}
    write(p, frontmatter.set_fields(read(p), updates))
    return p


def plan_understand(project: Project, work_id: str, understood: bool) -> Path:
    """Record in `기획.md` whether the person followed the plan (asked when planning ends).

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".
        understood: True when the person followed the plan, False when they handed it over.

    Returns:
        The plan document.

    Raises:
        ValueError: The work is not in progress or has no `기획.md`.

    Example:
        >>> plan_understand(project, "W-012", True).name  # doctest: +SKIP
        '기획.md'
    """
    folder = project.find_work(work_id, include_archive=False)
    p = project.doc_path(folder, "plan") if folder else None
    if p is None or not p.exists():
        raise ValueError(msg("{work_id} has no {file}", work_id=work_id, file=project.names.file("plan")))
    write(p, frontmatter.set_fields(read(p), {UNDERSTOOD: YES if understood else NO}))
    return p


def understood(project: Project, work_id: str) -> bool | None:
    """Tell whether the person followed a work: the design's mark, else the plan's.

    A small design that passes without asking carries no mark, so it follows the plan's; a design
    asked about later has the last word.

    Args:
        project: The project.
        work_id: The work, e.g. "W-012".

    Returns:
        True when followed, False when handed over, None when it was never asked (or the work is not found).

    Example:
        >>> understood(project, "W-012")  # doctest: +SKIP
        False
    """
    folder = project.find_work(work_id)
    if folder is None:
        return None
    for role in ("design", "plan"):
        p = project.doc_path(folder, role)
        value = frontmatter.parse(read(p)).meta.get(UNDERSTOOD) if p.exists() else None
        if value in (True, YES):  # a hand-written bare yes is read as true by YAML
            return True
        if value in (False, NO):
            return False
    return None
