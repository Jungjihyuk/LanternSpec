"""`lantern map` — rewrite the MOC's folder blocks from the folder state (/l-map).

Only the part between `<!-- l-map:start -->` and `<!-- l-map:end -->` is rewritten;
whatever a person wrote outside the marks is left alone.
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter
from ..core.messages import msg
from ..core.names import WORK_DOCS
from ..core.project import Project, nfc, now_minute, read, wikilink, work_id_of, work_name_of, write
from ..core.taskfile import parse_criteria, parse_tasks

START, END = "<!-- l-map:start -->", "<!-- l-map:end -->"

# (folder key, role, template doc names, more templates than listed, command) — English text; msg() translates it
FOLDER_ROLES: list[tuple[str, str, tuple[str, ...], bool, str]] = [
    ("templates", "The writing structure people set (templates)", (), False, "/l-template"),
    ("ideas", "Thoughts that came up. Not a work yet", ("idea",), False, "/l-idea"),
    (
        "works",
        "One feature · change = one folder. The only place edited while working",
        ("plan", "design", "tasks", "record"),
        False,
        "/l-plan → /l-design → /l-task → /l-build",
    ),
    (
        "current",
        "How the system looks now. Updated only when a work finishes",
        ("project_definition",),
        True,
        "/l-build (update) · /l-sync",
    ),
    ("ops", "Retros · reports · meeting notes", ("meeting",), False, "/l-report"),
    ("legacy", "(Brownfield) the original legacy documents. Never edited", ("legacy_map",), False, "/l-init · /l-template migrate"),
    ("debt", "Understanding-debt ledger. One card = one debt", ("debt_card",), False, "/l-learn"),
]


def _status_of(path: Path) -> str:
    try:
        return frontmatter.as_str(frontmatter.parse(read(path)).meta.get("status"))
    except OSError:
        return ""


def _md_files(folder: Path, recursive: bool = False) -> list[Path]:
    if not folder.exists():
        return []
    it = folder.rglob("*.md") if recursive else folder.glob("*.md")
    return sorted(p for p in it if not any(x.startswith(".") for x in p.parts))


def build_block(project: Project) -> str:
    """Build the generated part of the MOC from the folders as they are now.

    It lists the folders with their roles, current-state documents, works by stage,
    archived works, ideas, decisions, shortcuts and the commands.

    Args:
        project: The project.

    Returns:
        The block's Markdown (without the marks), starting with a "generated" line.

    Example:
        >>> build_block(project).splitlines()[2]  # doctest: +SKIP
        '## 폴더'
    """
    lines: list[str] = [msg("> ⚙️ Generated — `lantern map` · as of {now_minute}", now_minute=now_minute()), ""]
    # folder table
    lines += [msg("## Folders"), msg("| Folder | Role | Documents | Template | Command |"), "|---|---|---|---|---|"]
    for key, role, docs, more, cmd in FOLDER_ROLES:
        folder = project.folder(key)
        if not folder.exists():
            continue
        count = len(_md_files(folder, recursive=True))
        tmpl = " · ".join(project.names.doc(d) for d in docs) or "—"
        if more:
            tmpl = msg("{name} and more", name=tmpl)
        lines.append(f"| {project.names.folder(key)} | {msg(role)} | {count} | {tmpl} | `{msg(cmd)}` |")
    lines.append("")

    # current state
    current = project.folder("current")
    if current.exists():
        lines += [msg("## 📘 Current state — how the system looks now")]
        for p in _md_files(current, recursive=True):
            st = _status_of(p)
            inactive = project.enums.value("current_status", "inactive")
            mark = " " + project.enums.label("current_status", "inactive") if st == inactive else ""
            lines.append(f"- {wikilink(project, p, nfc(p.stem))}{mark}")
        lines.append("")

    # works — view by stage
    works = project.work_dirs()
    lines += [msg("## 📦 Works in progress — by stage")]
    if not works:
        lines.append(msg("- (nothing yet — start with `/l-plan`)"))
    else:
        lines += [msg("| Work | Stage | 📋 Plan | 📐 Design | ✅ Tasks | 🔨 Log |"), "|---|---|---|---|---|---|"]
        for w in works:
            wid, name = work_id_of(w), work_name_of(w)
            plan = project.doc_path(w, "plan")
            stage = _status_of(plan) if plan.exists() else ""
            cells = []
            for role in WORK_DOCS:
                p = project.doc_path(w, role)
                if not p.exists():
                    cells.append("—")
                    continue
                extra = ""
                if role == "plan":
                    acs = parse_criteria(read(p))
                    if acs:
                        extra = f" (AC {sum(a.done for a in acs)}/{len(acs)})"
                if role == "tasks":
                    ts = parse_tasks(read(p), project.names)
                    if ts:
                        extra = f" ({sum(t.done for t in ts)}/{len(ts)})"
                if role == "design":
                    approved = frontmatter.parse(read(p)).meta.get("approved")
                    extra = msg(" ✅ approved") if approved else msg(" ⏳ awaiting approval")
                cells.append(wikilink(project, p, p.stem, table=True) + extra)
            lines.append(f"| {wid} {name} | {project.enums['work_status'].labelled(stage) if stage else ''} | " + " | ".join(cells) + " |")
    lines.append("")

    archive = project.work_dirs(include_archive=True)
    done = [w for w in archive if w not in works]
    if done:
        lines += [msg("## 🗄 Archived works")]
        for w in done:
            lines.append(f"- {wikilink(project, project.doc_path(w, 'plan'), work_id_of(w) + ' ' + work_name_of(w))}")
        lines.append("")

    # ideas
    ideas = _md_files(project.folder("ideas"))
    if ideas:
        lines += [msg("## 💡 Ideas"), msg("| Idea | Kind | Status |"), "|---|---|---|"]
        for p in ideas:
            meta = frontmatter.parse(read(p)).meta
            lines.append(f"| {wikilink(project, p, nfc(p.stem), table=True)} | {meta.get('kind', '')} | {meta.get('status', '')} |")
        lines.append("")

    # decisions
    adrs = [p for p in _md_files(project.folder("decisions")) if nfc(p.name).startswith("ADR-")]
    if adrs:
        lines += [msg("## 📝 Decisions")]
        for p in adrs:
            lines.append(f"- {wikilink(project, p, nfc(p.stem))} — {_status_of(p)}")
        lines.append("")

    # debt + reports
    extras = []
    status = project.folder("debt") / project.names.file("debt_status")
    if status.exists():
        extras.append(f"- 📒 {wikilink(project, status, project.names.doc('debt_status'))}")
    report = project.folder("reports") / project.names.file("report")
    if report.exists():
        extras.append(f"- 📊 {wikilink(project, report, msg('Status report'))}")
    legacy_map = project.folder("legacy") / project.names.file("legacy_map")
    if legacy_map.exists():
        extras.append(f"- 🗂 {wikilink(project, legacy_map, project.names.doc('legacy_map'))}")
    if extras:
        lines += [msg("## Shortcuts"), *extras, ""]

    lines += [
        msg("## Commands"),
        msg("| To do this | Command |"),
        "|---|---|",
        msg("| Capture a thought | `/l-idea` |"),
        msg("| Plan → design → tasks → build | `/l-plan` → `/l-design` → `/l-task` → `/l-build` |"),
        msg("| An unfamiliar technology | `/l-learn` |"),
        msg("| Where things stand | `/l-report` |"),
        msg("| Make · refine templates | `/l-template` |"),
        msg("| Check formats | `/l-check` |"),
        msg("| Align docs ↔ code | `/l-sync` |"),
        msg("| An important decision | `/l-adr` |"),
    ]
    return "\n".join(lines).rstrip()


def run(project: Project) -> Path:
    """Rewrite the MOC's generated block, creating the MOC from its template when missing.

    The file is left untouched when only the timestamp would change.

    Args:
        project: The project.

    Returns:
        The MOC file.

    Example:
        >>> run(project).name  # doctest: +SKIP
        '개발문서 MOC.md'
    """
    moc = project.moc
    if not moc.exists():
        from ..work.scaffold import create_from_template

        create_from_template(project, project.names.doc("moc"), moc)
    text = read(moc)
    block = build_block(project)
    s, e = text.find(START), text.find(END)
    if s == -1 or e == -1 or e < s:
        text = text.rstrip() + f"\n\n{START}\n{block}\n{END}\n"
    else:
        old = text[s + len(START) : e].strip()
        if _without_stamp(old) == _without_stamp(block):
            return moc  # nothing changed — keep the old timestamp (no noisy diffs)
        text = text[: s + len(START)] + "\n" + block + "\n" + text[e:]
    write(moc, text)
    return moc


def _without_stamp(block: str) -> str:
    return "\n".join(l for l in block.split("\n") if not l.startswith(msg("> ⚙️ Generated")))
