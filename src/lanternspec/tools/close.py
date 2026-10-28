"""`lantern close` — every skill's common close: check → map → debt status → run record.

Works for every tool, with or without agent hooks.
"""

from __future__ import annotations

from ..core.project import Project


def close(
    project: Project,
    skill: str,
    work: str | None = None,
    start: str | None = None,
    model: str | None = None,
    check: bool = True,
    do_map: bool = True,
) -> list[str]:
    """Close a skill run: check the changed documents, refresh the MOC and debt status, and log the run.

    Args:
        project: The project.
        skill: The skill that ran, e.g. "l-build".
        work: The work it ran for.
        start: When it started (ISO time).
        model: The model in use.
        check: Check the documents.
        do_map: Refresh the MOC.

    Returns:
        One line per step.

    Example:
        >>> close(project, "l-build", work="W-012")[-1]  # doctest: +SKIP
        '✔ 실행 기록 — l-build · W-012 (.lantern/runs.jsonl)'
    """
    from ..check import check_docs
    from ..report import doc_map
    from . import runlog

    lines: list[str] = []
    counts = {"error": 0, "warn": 0, "info": 0}
    if check and project.docs.exists():
        changed = check_docs.changed_docs(project)
        rep = check_docs.run(project, changed if changed else None)
        counts = rep.counts()
        shown = [f for f in rep.findings if f.level != "info"]
        if shown:
            lines.append(check_docs.Report(shown, rep.files).format(show_info=False))
        else:
            lines.append(f"✔ check — 문서 {rep.files}개 양식에 맞음" + (f" (참고 {counts['info']}개)" if counts["info"] else ""))
    if do_map and project.docs.exists():
        doc_map.run(project)
        lines.append("✔ map — MOC 갱신")
    if project.folder("debt").exists():
        from ..learn.debt import write_status

        write_status(project)
    from ..report.evaluate import config_snapshot

    runlog.skill_run(project, skill, start, model, {"work": work, "check": counts, "config": config_snapshot(project)})
    lines.append(f"✔ 실행 기록 — {skill}{' · ' + work if work else ''} (.lantern/runs.jsonl)")
    return lines
