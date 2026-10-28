"""`lantern pack W-012` — work pack: the work folder + only the related current-state parts.

A one-off summary for the AI. Regenerated every time, never edited, git-ignored.

Not here:
    - choosing the next task → work/tasks.py (next_task)
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core import frontmatter
from ..core.links import Resolver, iter_links
from ..core.messages import msg
from ..core.names import WORK_DOCS
from ..core.project import Project, now_minute, read, work_id_of, work_name_of, write
from .tasks import next_task


def _glance(text: str) -> str:
    body = frontmatter.parse(text).body
    m = re.search(r"^>\s*\[!abstract\][^\n]*\n((?:>.*\n?)+)", body, re.M)
    return "\n".join(l.lstrip(">").strip() for l in m.group(1).split("\n") if l.strip(">").strip()) if m else ""


def _strip_guides(text: str) -> str:
    """Drop frontmatter and writing guides — the AI needs content, not instructions."""
    body = frontmatter.parse(text).body
    out: list[str] = []
    skipping = False
    for line in body.split("\n"):
        if line.startswith("> [!guide]"):
            skipping = True
            continue
        if skipping and line.startswith(">"):
            continue
        skipping = False
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def build(project: Project, work_id: str) -> str:
    """Build the text of a work pack.

    It holds the working rules, the next task, the work's four documents without writing guides,
    the project definition's at-a-glance part, the data source when the design touches data,
    and every current-state document the work links to.

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".

    Returns:
        The pack as Markdown.

    Raises:
        ValueError: The work is not in progress.

    Example:
        >>> build(project, "W-012").splitlines()[0]  # doctest: +SKIP
        '# 📦 작업 꾸러미 — W-012 로그인'
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    wid = work_id_of(folder)
    parts: list[str] = [
        msg("# 📦 Work pack — {wid} {work_name_of}", wid=wid, work_name_of=work_name_of(folder)),
        msg(
            "> Generated {now_minute} · `lantern pack {wid}` · use once and throw away. Don't edit it; edit the source documents.",
            now_minute=now_minute(),
            wid=wid,
        ),
        "",
        msg("## Rules"),
        msg("- One task = one commit, `[task ID]` at the end of the message · start/finish with `lantern task start|done`"),
        msg(
            "- A big change not in the design · `{marker}` · a test failing 3 times · a real DB migration → report right away and stop",
            marker=project.names.marker("unknown"),
        ),
        msg(
            "- Report cycle: {get} · merge approval: {get2}",
            get=project.profile.get("build.report_cycle"),
            get2=project.profile.get("build.merge_approval"),
        ),
    ]
    nxt = next_task(project, wid)
    if nxt.task:
        parts += [
            "",
            msg("## ▶ Next task: {id} {title}", id=nxt.task.id, title=nxt.task.title),
            msg("- Size {value} · criteria {value2}", value=nxt.task.size or "?", value2=", ".join(nxt.task.criteria) or "—"),
        ]
    elif nxt.all_done:
        parts += ["", msg("## ✅ All tasks done — time to update the current state")]
    if nxt.skipped:
        parts += ["", msg("### Tasks that can't start yet")] + [f"- {tid}: {why}" for tid, why in nxt.skipped]

    linked: list[Path] = []
    resolver = Resolver(project.docs)
    n = project.names
    for role in WORK_DOCS:
        p = project.doc_path(folder, role)
        if not p.exists():
            continue
        text = read(p)
        parts += ["", f"---\n## 📄 {p.name}", _strip_guides(text)]
        for link in iter_links(text):
            target = resolver.resolve(link, p)
            if target and target.suffix == ".md" and folder not in target.parents and target not in linked:
                linked.append(target)
    # current state: project definition glance always, linked docs in full (data doc if the design touches data)
    current = project.folder("current")
    definition = current / n.file("project_definition")
    parts += ["", msg("---\n## 📘 Current state (relevant parts only)")]
    if definition.exists():
        parts += [f"### {n.doc('project_definition')} — {n.marker('glance')}", _glance(read(definition)) or msg("(empty)")]
    design = project.doc_path(folder, "design")
    if design.exists() and "```dbml" in read(design):
        schema = current / n.folder("data") / "schema.dbml"
        if schema.exists():
            parts += [msg("### Data source (schema.dbml)"), "```dbml", read(schema).strip(), "```"]
    for p in linked:
        if p == definition:
            continue
        parts += [f"### {project.docs_rel(p)}", _strip_guides(read(p))]
    return "\n".join(parts).rstrip() + "\n"


def run(project: Project, work_id: str, out: Path | None = None) -> Path:
    """Build a work pack and write it (`.lantern/pack/W-012.md` by default).

    Args:
        project: The project.
        work_id: A work in progress.
        out: Where to write instead of the default.

    Returns:
        The written file.

    Raises:
        ValueError: The work is not in progress.

    Example:
        >>> run(project, "W-012").name  # doctest: +SKIP
        'W-012.md'
    """
    text = build(project, work_id)
    dest = out or (project.state / "pack" / f"{work_id.upper()}.md")
    from ..core.state import ensure_state_dir

    ensure_state_dir(project)
    write(dest, text)
    return dest
