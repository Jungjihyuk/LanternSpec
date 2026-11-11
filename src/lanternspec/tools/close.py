"""`lantern close` — every skill's common close: check → map → debt status → status report → run record → (asked) commit.

Works for every tool, with or without agent hooks.
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter
from ..core.messages import msg
from ..core.project import Project, git, git_out, read, today

# what each skill's commit is called, by the document role it writes
COMMIT_DOC = {"l-plan": "plan", "l-design": "design", "l-task": "tasks", "l-adr": "adr"}


def close(
    project: Project,
    skill: str,
    work: str | None = None,
    start: str | None = None,
    model: str | None = None,
    check: bool = True,
    do_map: bool = True,
    commit: bool = False,
) -> list[str]:
    """Close a skill run: check changed documents, refresh the MOC, debt status and status report, show glossary candidates, log the run.

    The status report is refreshed so its kanban and timeline follow every skill; its three summary lines are kept
    (only /l-report writes new ones).

    Args:
        project: The project.
        skill: The skill that ran, e.g. "l-build".
        work: The work it ran for.
        start: When it started (ISO time).
        model: The model in use.
        check: Check the documents.
        do_map: Refresh the MOC.
        commit: Commit the work's documents (`commit_work_docs`), unless lantern.yaml docs.commit is manual.

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
        rep = check_docs.run(project, changed if changed else None, templates=True)
        counts = rep.counts()
        shown = [f for f in rep.findings if f.level != "info"]
        if shown:
            lines.append(check_docs.Report(shown, rep.files).format(show_info=False))
        else:
            lines.append(
                msg("✔ check — {files} documents are well-formed", files=rep.files)
                + (msg(" ({info} notes)", info=counts["info"]) if counts["info"] else "")
            )
    if do_map and project.docs.exists():
        doc_map.run(project)
        lines.append(msg("✔ map — MOC updated"))
    if project.folder("debt").exists():
        from ..learn.debt import write_status

        write_status(project)
    if do_map and project.docs.exists():
        from ..report import views

        views.run(project)
        lines.append(msg("✔ report — status report updated"))
    from ..refs.terms import candidates

    waiting = candidates(project)
    if waiting:
        items = ", ".join(f"{c['term']} ({c['asked']})" for c in waiting[:5])
        lines.append(
            msg(
                "📘 Glossary candidates — words asked about that the documents use: {items}. "
                'Show each with a draft meaning and ask; approved → lantern ref glossary "<term>" --meaning "…", '
                'not a project word → lantern ref candidate "<term>" --drop',
                items=items,
            )
        )
    from ..report.evaluate import config_snapshot

    runlog.skill_run(project, skill, start, model, {"work": work, "check": counts, "config": config_snapshot(project)})
    lines.append(msg("✔ Run recorded — {skill}{value} (.lantern/runs.jsonl)", skill=skill, value=" · " + work if work else ""))
    if commit:
        lines.append(commit_work_docs(project, skill, work))
    return lines


def work_doc_paths(project: Project, work: str) -> list[Path]:
    """The documents a work owns: its folder, idea cards, the decision records its design lists, and the pages close refreshes.

    Args:
        project: The project.
        work: The work, e.g. "W-012".

    Returns:
        The paths (the ones that exist).

    Example:
        >>> [p.name for p in work_doc_paths(project, "W-012")]  # doctest: +SKIP
        ['W-012 로그인', 'IDEA-003 카톡 로그인.md', 'ADR-002 세션 방식.md', '개발문서 MOC.md']
    """
    folder = project.find_work(work, include_archive=False)
    if folder is None:
        return []
    paths = [folder, *_linked_ideas(project, project.doc_path(folder, "plan"))]
    design = project.doc_path(folder, "design")
    if design.exists():
        adrs = frontmatter.parse(read(design)).meta.get("adr")
        for adr in adrs if isinstance(adrs, list) else [adrs] if adrs else []:
            found = project.find_by_id(str(adr))
            if found:
                paths.append(found)
    paths += _refreshed_pages(project)
    return [p for p in paths if p.exists()]


def _refreshed_pages(project: Project) -> list[Path]:
    """The pages close itself rewrites: the MOC, debt status, the status report and today's copy of it."""
    return [
        project.moc,
        project.folder("debt") / project.names.file("debt_status"),
        project.folder("reports") / project.names.file("report"),
        project.folder("past_reports") / f"{today()}.md",
    ]


def _linked_ideas(project: Project, plan: Path) -> list[Path]:
    """Idea cards linked with the plan in either direction (the plan names its idea, a worked idea names the plan)."""
    ideas = project.folder("ideas")
    if not plan.exists() or not ideas.exists():
        return []
    from ..core.links import Resolver, iter_links

    resolver = Resolver(project.docs)

    def targets(doc: Path) -> set[Path]:
        links = frontmatter.as_list(frontmatter.parse(read(doc)).meta.get("links"))
        found = (resolver.resolve(link, doc) for link in iter_links("\n".join(map(str, links))))
        return {p.resolve() for p in found if p}

    from_plan = targets(plan)
    return [card for card in sorted(ideas.rglob("*.md")) if card.resolve() in from_plan or plan.resolve() in targets(card)]


def commit_work_docs(project: Project, skill: str, work: str | None) -> str:
    """Commit only the documents a work owns, leaving everything else as it is.

    Other works' documents, editor settings and code stay out, so a session running in
    parallel with others never commits their files. In local mode the commit goes to the
    documents branch. With lantern.yaml `docs.commit: manual` nothing is committed.

    Args:
        project: The project.
        skill: The skill closing, e.g. "l-design" (it names the commit).
        work: The work, e.g. "W-012"; nothing is committed without one.

    Returns:
        One line saying what happened.

    Example:
        >>> commit_work_docs(project, "l-design", "W-012")  # doctest: +SKIP
        '✔ 커밋 — docs: W-012 설계 [W-012]'
    """
    if not work:
        return msg("ℹ --commit needs --work, so nothing was committed")
    wid = work.upper()
    cwd = project.docs_git_cwd()
    paths = work_doc_paths(project, wid)
    rels = [p.relative_to(cwd).as_posix() for p in paths]
    # the pages close refreshes on every run go along with the work's own changes, never in a commit of their own
    refreshed = {p.resolve() for p in _refreshed_pages(project)}
    own = [p.relative_to(cwd).as_posix() for p in paths if p.resolve() not in refreshed]
    changed = git_out(["status", "--porcelain", "--untracked-files=all", "--", *own], cwd) if own else ""
    if not changed:
        return msg("ℹ Nothing to commit for {work}", work=wid)
    if project.profile.get("docs.commit") == "manual":
        return msg("ℹ docs.commit: manual — documents to commit: {items}", items=", ".join(rels))
    role = COMMIT_DOC.get(skill)
    message = f"docs: {wid} {project.names.doc(role) if role else skill} [{wid}]"
    r = git(["add", "--", *rels], cwd)
    if r.returncode == 0:
        r = git(["commit", "-m", message, "--", *rels], cwd)
    if r.returncode != 0:
        return msg("⚠ Couldn't commit: {strip}", strip=(r.stderr or r.stdout).strip())
    return msg("✔ Committed — {message}", message=message)
