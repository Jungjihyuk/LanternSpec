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
        raise ValueError(f"진행 중인 작업 {work_id}를 찾지 못했습니다")
    wid = work_id_of(folder)
    parts: list[str] = [
        f"# 📦 작업 꾸러미 — {wid} {work_name_of(folder)}",
        f"> 자동 생성 {now_minute()} · `lantern pack {wid}` · 한 번 쓰고 버린다. 고치지 말고 원본 문서를 고친다.",
        "",
        "## 규칙",
        "- 할 일 하나 = 커밋 하나, 메시지 끝에 `[할 일 ID]` · 시작/완료는 `lantern task start|done`",
        f"- 설계에 없는 큰 변경 · `{project.names.marker('unknown')}` · 테스트 3번 실패 · 실제 DB 마이그레이션 → 바로 보고하고 멈춘다",
        f"- 보고 주기: {project.profile.get('build.report_cycle')} · 반영 승인: {project.profile.get('build.merge_approval')}",
    ]
    nxt = next_task(project, wid)
    if nxt.task:
        parts += [
            "",
            f"## ▶ 다음 할 일: {nxt.task.id} {nxt.task.title}",
            f"- 크기 {nxt.task.size or '?'} · 기준 {', '.join(nxt.task.criteria) or '—'}",
        ]
    elif nxt.all_done:
        parts += ["", "## ✅ 모든 할 일 완료 — 현재 상태 반영 단계"]
    if nxt.skipped:
        parts += ["", "### 지금 시작할 수 없는 할 일"] + [f"- {tid}: {why}" for tid, why in nxt.skipped]

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
    parts += ["", "---\n## 📘 현재 상태 (관련 부분만)"]
    if definition.exists():
        parts += [f"### {n.doc('project_definition')} — {n.marker('glance')}", _glance(read(definition)) or "(비어 있음)"]
    design = project.doc_path(folder, "design")
    if design.exists() and "```dbml" in read(design):
        schema = current / n.folder("data") / "schema.dbml"
        if schema.exists():
            parts += ["### 데이터 원본 (schema.dbml)", "```dbml", read(schema).strip(), "```"]
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
