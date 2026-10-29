"""`lantern report` — write the views out as plain text.

`4. 운영 기록/보고/현황.md` is always the latest; each run also writes
`보고/지난 보고/YYYY-MM-DD.md` (one per day, same day overwrites) with a comparison
to the previous report. The AI writes only the three summary lines.

Not here:
    - the docs-vs-code drift itself → report/scan.py
    - AI work evaluation numbers → report/evaluate.py
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from ..core import frontmatter
from ..core.messages import msg
from ..core.project import Project, git_out, nfc, now_minute, read, today, wikilink, work_id_of, work_name_of, write
from ..core.taskfile import Task, TaskGraph, parse_criteria, parse_tasks
from ..learn import debt as debt_mod

VIEWS = ["kanban", "timeline", "domain", "trace", "debt", "sync", "eval"]
VIEW_TITLE = {  # English; msg() translates them
    "kanban": "🗂 Kanban",
    "timeline": "📅 Timeline (WBS)",
    "domain": "🧩 By domain · requirement",
    "trace": "🔗 Traceability",
    "debt": "📒 Debt Status",
    "sync": "🔄 Doc-code alignment",
    "eval": "📊 AI work evaluation",
}
SUM_START, SUM_END = "<!-- l-report:summary:start -->", "<!-- l-report:summary:end -->"
SIZE_DAYS = {"S": 1, "M": 2, "L": 3}


def _work_tasks(project: Project, w: Path) -> list[Task]:
    tf = project.doc_path(w, "tasks")
    return parse_tasks(read(tf), project.names) if tf.exists() else []


def _meta(p: Path) -> dict:
    return frontmatter.parse(read(p)).meta if p.exists() else {}


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


# --------------------------------------------------------------------------- views


def kanban(project: Project) -> str:
    """Draw the tasks of works in progress as a kanban table (to do · blocked · in progress · done).

    Args:
        project: The project.

    Returns:
        A Markdown table; a short note when there are no tasks.

    Example:
        >>> kanban(project).splitlines()[0]  # doctest: +SKIP
        '| 📥 할 일 (1) | ⛔ 막힘 (0) | ▶ 진행 중 (1) | ✅ 완료 (2) |'
    """
    cols: dict[str, list[str]] = {"todo": [], "blocked": [], "doing": [], "done": []}
    for w in project.work_dirs():
        tasks = _work_tasks(project, w)
        graph = TaskGraph(tasks)
        for t in tasks:
            label = f"{t.id} {t.title}" + (f" [{t.size}]" if t.size else "") + (f" @{t.attrs['owner']}" if t.attrs.get("owner") else "")
            if t.done:
                cols["done"].append(label)
            elif t.started:
                cols["doing"].append(label)
            elif graph.blocked_reason(t):
                cols["blocked"].append(f"{label} — {graph.blocked_reason(t)}")
            else:
                cols["todo"].append(label)
    rows = max((len(v) for v in cols.values()), default=0)
    if rows == 0:
        return msg("_No tasks in progress._")
    lines = [
        msg(
            "| 📥 To do ({count}) | ⛔ Blocked ({count2}) | ▶ Doing ({count3}) | ✅ Done ({count4}) |",
            count=len(cols["todo"]),
            count2=len(cols["blocked"]),
            count3=len(cols["doing"]),
            count4=len(cols["done"]),
        ),
        "|---|---|---|---|",
    ]
    for i in range(rows):
        lines.append("| " + " | ".join(_cell(cols[k][i]) if i < len(cols[k]) else "" for k in ("todo", "blocked", "doing", "done")) + " |")
    return "\n".join(lines)


def _gantt_name(s: str) -> str:
    return re.sub(r"[:#;]", " ", s).strip()[:60]


def _parse_dt(s: str) -> _dt.datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def timeline(project: Project) -> str:
    """Draw every work (archived ones too) as a Mermaid Gantt chart.

    Tasks use their actual times when they have them, then planned dates, then their order and size
    (S = 1 day · M = 2 · L = 3). The idea a work came from shows as a milestone.

    Args:
        project: The project.

    Returns:
        The Mermaid block with a note on how it was drawn; a short note when there are no works.

    Example:
        >>> timeline(project).splitlines()[1]  # doctest: +SKIP
        'gantt'
    """
    works = project.work_dirs(include_archive=True)
    if not works:
        return msg("_No works._")
    lines = ["```mermaid", "gantt", "  dateFormat YYYY-MM-DD HH:mm", "  axisFormat %m-%d", "  todayMarker on"]
    any_task = False
    for w in works:
        wid = work_id_of(w)
        tasks = _work_tasks(project, w)
        plan_meta = _meta(project.doc_path(w, "plan"))
        lines.append(f"  section {_gantt_name(wid + ' ' + work_name_of(w))}")
        # idea → work: when did the idea appear?
        for link in frontmatter.as_list(plan_meta.get("links")):
            m = re.search(r"(IDEA-\d{3,})", str(link))
            if m:
                idea = project.find_by_id(m.group(1))
                created = frontmatter.as_str(_meta(idea).get("created")) if idea else ""
                if created:
                    lines.append(f"  💡 {m.group(1)} :milestone, {wid.lower().replace('-', '')}idea, {created} 00:00, 0d")
        prev_id: str | None = None
        cursor = _parse_dt(frontmatter.as_str(plan_meta.get("created")) or today()) or _dt.datetime.now()
        for t in tasks:
            any_task = True
            tid = t.id.lower().replace("-", "")
            name = _gantt_name(f"{t.id.split('-')[-1]} {t.title}")
            start, end = _parse_dt(t.started), _parse_dt(t.finished)
            planned_s, planned_e = _parse_dt(t.attrs.get("start_plan", "")), _parse_dt(t.attrs.get("due_plan", ""))
            tag = "done, " if t.done else ("active, " if t.started else "")
            if start and end:
                if end <= start:
                    end = start + _dt.timedelta(minutes=30)
                lines.append(f"  {name} :{tag}{tid}, {start:%Y-%m-%d %H:%M}, {end:%Y-%m-%d %H:%M}")
                cursor = end
            elif start:
                lines.append(f"  {name} :{tag}{tid}, {start:%Y-%m-%d %H:%M}, {SIZE_DAYS.get(t.size, 1)}d")
                cursor = start + _dt.timedelta(days=SIZE_DAYS.get(t.size, 1))
            elif planned_s:
                end_p = planned_e or planned_s + _dt.timedelta(days=SIZE_DAYS.get(t.size, 1))
                lines.append(f"  {name} :{tag}{tid}, {planned_s:%Y-%m-%d %H:%M}, {end_p:%Y-%m-%d %H:%M}")
                cursor = end_p
            elif prev_id:
                lines.append(f"  {name} :{tag}{tid}, after {prev_id}, {SIZE_DAYS.get(t.size, 1)}d")
            else:
                lines.append(f"  {name} :{tag}{tid}, {cursor:%Y-%m-%d %H:%M}, {SIZE_DAYS.get(t.size, 1)}d")
            prev_id = tid
        if not tasks:
            created = frontmatter.as_str(plan_meta.get("created")) or today()
            lines.append(
                msg(
                    "  {gantt_name} plan :milestone, {replace}m, {created} 00:00, 0d",
                    gantt_name=_gantt_name(wid),
                    replace=wid.lower().replace("-", ""),
                    created=created,
                )
            )
    lines.append("```")
    note = "" if any_task else msg("\n_No tasks yet, so only the start of each work is shown._")
    return (
        "\n".join(lines)
        + msg(
            "\n\n> Without planned dates it is drawn from task order and size (S=1 day · M=2 days · L=3 "
            "days); once actual times exist, from those."
        )
        + note
    )


def domain(project: Project) -> str:
    """Group works by their plan's `domain`, with stage and progress.

    Args:
        project: The project.

    Returns:
        A Markdown table (domain · work · stage · criteria done · tasks done); a short note when there are no works.

    Example:
        >>> domain(project).splitlines()[0]  # doctest: +SKIP
        '| 도메인 | 작업 | 단계 | 수락 기준 | 할 일 |'
    """
    groups: dict[str, list[str]] = {}
    for w in project.work_dirs(include_archive=True):
        meta = _meta(project.doc_path(w, "plan"))
        dom = str(meta.get("domain") or "")
        if not dom or "{{" in dom:
            dom = msg("(no domain)")
        acs = parse_criteria(read(project.doc_path(w, "plan"))) if (project.doc_path(w, "plan")).exists() else []
        tasks = _work_tasks(project, w)
        row = (
            f"| {_cell(dom)} | {wikilink(project, project.doc_path(w, 'plan'), work_id_of(w) + ' ' + work_name_of(w), table=True)} | "
            f"{meta.get('status', '')} | {sum(a.done for a in acs)}/{len(acs)} | {sum(t.done for t in tasks)}/{len(tasks)} |"
        )
        groups.setdefault(dom, []).append(row)
    if not groups:
        return msg("_No works._")
    lines = [msg("| Domain | Work | Stage | Acceptance criteria | Tasks |"), "|---|---|---|---|---|"]
    for dom in sorted(groups):
        lines += groups[dom]
    return "\n".join(lines)


def trace(project: Project) -> str:
    """Trace each idea to the works it became and their commits.

    Args:
        project: The project.

    Returns:
        A Markdown table (idea · status · work · commit count · last commit); a short note when there are no ideas.

    Example:
        >>> trace(project).splitlines()[0]  # doctest: +SKIP
        '| 아이디어 | 상태 | 작업 | 커밋 | 마지막 커밋 |'
    """
    rows = [msg("| Idea | Status | Work | Commits | Last commit |"), "|---|---|---|---|---|"]
    ideas_folder = project.folder("ideas")
    works = project.work_dirs(include_archive=True)
    work_by_idea: dict[str, list[Path]] = {}
    for w in works:
        for link in frontmatter.as_list(_meta(project.doc_path(w, "plan")).get("links")):
            m = re.search(r"(IDEA-\d{3,})", str(link))
            if m:
                work_by_idea.setdefault(m.group(1), []).append(w)
    ideas = sorted(ideas_folder.glob("*.md")) if ideas_folder.exists() else []
    for idea in ideas:
        iid = nfc(idea.stem).split(" ")[0]
        meta = _meta(idea)
        linked = work_by_idea.get(iid, [])
        if not linked:
            rows.append(f"| {wikilink(project, idea, nfc(idea.stem), table=True)} | {meta.get('status', '')} | — | — | — |")
            continue
        for w in linked:
            wid = work_id_of(w)
            log = git_out(["log", "--all", "--no-merges", "--format=%h %ad", "--date=short", f"--grep={wid}"], project.root).splitlines()
            last = log[0] if log else "—"
            rows.append(
                f"| {wikilink(project, idea, nfc(idea.stem), table=True)} | {meta.get('status', '')} | "
                f"{wikilink(project, project.doc_path(w, 'plan'), wid, table=True)} | {len(log)} | {last} |"
            )
    if len(rows) == 2:
        return msg("_No ideas._")
    return "\n".join(rows)


def debt_view(project: Project) -> str:
    """Refresh the debt status page and summarize it.

    Args:
        project: The project.

    Returns:
        Open and resolved counts, a link to the status page and the kind × topic table;
        a short note when the learning line is off.

    Example:
        >>> debt_view(project).splitlines()[0]  # doctest: +SKIP
        '열린 부채 **3개** · ✅ 해결 1개 — 자세히: [[📒 부채/부채 현황|부채 현황]]'
    """
    if not project.folder("debt").exists():
        return msg("_The learning track is off (lantern.yaml knowledge)._")
    debt_mod.write_status(project)
    s = debt_mod.stats(project)
    status = project.folder("debt") / project.names.file("debt_status")
    return msg(
        "Open debt **{open}** · {label} {resolved} — details: {wikilink}\n\n",
        open=s["open"],
        label=project.enums.label("debt_status", "resolved"),
        resolved=s["resolved"],
        wikilink=wikilink(project, status, project.names.doc("debt_status")),
    ) + debt_mod.status_markdown(project)


def sync_view(project: Project) -> tuple[str, int]:
    """Run the docs-vs-code drift scan for the report.

    Args:
        project: The project.

    Returns:
        The scan's text and its number of findings.

    Example:
        >>> sync_view(project)[1]  # doctest: +SKIP
        0
    """
    from . import scan

    res = scan.run(project, limit=100)
    return res.format(), res.total


# --------------------------------------------------------------------------- stats & compare


def collect_stats(project: Project, sync_total: int | None) -> dict:
    """Collect the numbers a report keeps in its frontmatter (and the next report compares against).

    Args:
        project: The project.
        sync_total: Number of drift findings; left out when None.

    Returns:
        tasks_done, tasks_total, works_active, works_archived, debt_open, debt_resolved, debt_total,
        approval_waiting (works whose design waits for approval) and, when given, sync_issues.

    Example:
        >>> collect_stats(project, None)["works_active"]  # doctest: +SKIP
        1
    """
    tasks_done = tasks_total = 0
    for w in project.work_dirs(include_archive=True):
        ts = _work_tasks(project, w)
        tasks_total += len(ts)
        tasks_done += sum(t.done for t in ts)
    active = project.work_dirs()
    approvals = [
        work_id_of(w) for w in active if project.doc_path(w, "design").exists() and not _meta(project.doc_path(w, "design")).get("approved")
    ]
    d = debt_mod.stats(project) if project.folder("debt").exists() else {"open": 0, "resolved": 0, "total": 0}
    s = {
        "tasks_done": tasks_done,
        "tasks_total": tasks_total,
        "works_active": len(active),
        "works_archived": len(project.work_dirs(include_archive=True)) - len(active),
        "debt_open": d["open"],
        "debt_resolved": d["resolved"],
        "debt_total": d["total"],
        "approval_waiting": approvals,
    }
    if sync_total is not None:
        s["sync_issues"] = sync_total
    return s


def _previous(project: Project) -> dict | None:
    folder = project.folder("past_reports")
    if not folder.exists():
        return None
    past = sorted(p for p in folder.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}$", p.stem) and p.stem < today())
    if not past:
        return None
    meta = _meta(past[-1])
    return {"date": past[-1].stem, "stats": meta.get("stats") or {}}


def compare(project: Project, cur: dict, prev: dict | None) -> str:
    """Compare the current numbers with the previous report.

    Args:
        project: The project.
        cur: Numbers from collect_stats.
        prev: The previous report's date and stats; None for the first report.

    Returns:
        One line with the changes in finished tasks, new debt and resolved debt.

    Example:
        >>> compare(project, stats, None)  # doctest: +SKIP
        '_첫 보고입니다 — 다음 보고부터 비교가 나옵니다._'
    """
    if not prev:
        return msg("_This is the first report — comparisons start with the next one._")
    p = prev["stats"]
    done = cur["tasks_done"] - int(p.get("tasks_done", 0))
    new_debt = cur["debt_total"] - int(p.get("debt_total", 0))
    resolved = cur["debt_resolved"] - int(p.get("debt_resolved", 0))
    return msg(
        "Since the last report ({date}): ✅ tasks done **{done:+d}** · 📒 new debt **{new_debt:+d}** "
        "· {label} debt **{resolved:+d}** · {works_active} works in progress",
        date=prev["date"],
        done=done,
        new_debt=new_debt,
        label=project.enums.label("debt_status", "resolved"),
        resolved=resolved,
        works_active=cur["works_active"],
    )


def _existing_summary(path: Path) -> str | None:
    if not path.exists():
        return None
    text = read(path)
    s, e = text.find(SUM_START), text.find(SUM_END)
    if s == -1 or e == -1:
        return None
    return text[s + len(SUM_START) : e].strip("\n")


def run(project: Project, views: list[str] | None = None, summary: list[str] | None = None) -> tuple[Path, Path]:
    """Write the report: `현황.md` (latest) and today's copy under `지난 보고/`.

    The three summary lines are kept from the previous `현황.md` unless new ones are given.

    Args:
        project: The project.
        views: Views to include; `report.views` when None.
        summary: Up to three summary lines written by the AI.

    Returns:
        The latest report and today's copy.

    Raises:
        ValueError: A view name is unknown.

    Example:
        >>> [p.name for p in run(project, ["kanban"])]  # doctest: +SKIP
        ['현황.md', '2026-10-28.md']
    """
    views = views or list(project.profile.get("report.views") or ["kanban", "timeline", "debt"])
    bad = [v for v in views if v not in VIEWS]
    if bad:
        raise ValueError(msg("Unknown view: {items} (available: {items2})", items=", ".join(bad), items2=", ".join(VIEWS)))
    current = project.folder("reports") / project.names.file("report")
    sections: list[str] = []
    sync_total: int | None = None
    for v in views:
        if v == "kanban":
            body = kanban(project)
        elif v == "timeline":
            body = timeline(project)
        elif v == "domain":
            body = domain(project)
        elif v == "trace":
            body = trace(project)
        elif v == "debt":
            body = debt_view(project)
        elif v == "eval":
            from .evaluate import markdown as eval_markdown

            body = eval_markdown(project)
        else:
            body, sync_total = sync_view(project)
        sections.append(f"## {msg(VIEW_TITLE[v])}\n\n{body}")
    if sync_total is None:  # stale docs are checked whenever the report is opened
        from . import scan

        sync_total = scan.run(project, limit=100).total
    stats = collect_stats(project, sync_total)
    prev = _previous(project)
    if summary:
        summary_text = "\n".join(
            f"{i}. {line.strip()}" if not re.match(r"^\d+\.", line.strip()) else line.strip() for i, line in enumerate(summary[:3], start=1)
        )
    else:
        summary_text = _existing_summary(current) or msg('> The AI fills in 3 lines: `lantern report --summary "…" "…" "…"`')
    waiting = stats["approval_waiting"]
    head = [
        msg("# 📊 Status Report"),
        "",
        msg(
            "> ⚙️ Generated — `lantern report` · **as of {now_minute}** · views: {items}",
            now_minute=now_minute(),
            items=", ".join(msg(VIEW_TITLE[v]) for v in views),
        ),
        "",
        f"> [!abstract] {project.names.marker('glance')}",
        msg(
            "> {works_active} works in progress · tasks {tasks_done}/{tasks_total} done · {debt_open} open debts",
            works_active=stats["works_active"],
            tasks_done=stats["tasks_done"],
            tasks_total=stats["tasks_total"],
            debt_open=stats["debt_open"],
        )
        + (msg(" · ⏳ design awaiting approval {items}", items=", ".join(waiting)) if waiting else "")
        + (
            msg(" · 🔄 {sync_issues} doc-code mismatches (`/l-sync`)", sync_issues=stats["sync_issues"]) if stats.get("sync_issues") else ""
        ),
        "",
        msg("## 3-line summary"),
        SUM_START,
        summary_text,
        SUM_END,
        "",
        msg("## Compared with the last report"),
        compare(project, stats, prev),
        "",
    ]
    body = "\n".join(head) + "\n" + "\n\n".join(sections) + "\n"
    meta = {
        "id": "OPS-report",
        "type": "report",
        "status": project.enums.value("current_status", "active"),
        "generated": True,
        "updated": today(),
        "views": views,
        "stats": stats,
    }
    write(current, frontmatter.render(meta, body))
    past = project.folder("past_reports") / f"{today()}.md"
    meta_past = dict(meta, id=f"OPS-report-{today()}")
    write(past, frontmatter.render(meta_past, body.replace(msg("# 📊 Status Report"), msg("# 📊 {today} Report", today=today()), 1)))
    return current, past
