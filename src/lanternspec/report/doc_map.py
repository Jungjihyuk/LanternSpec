"""`lantern map` — rewrite the MOC's folder blocks from the folder state (/l-map).

Only the part between `<!-- l-map:start -->` and `<!-- l-map:end -->` is rewritten;
whatever a person wrote outside the marks is left alone.
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter
from ..core.names import WORK_DOCS
from ..core.project import Project, nfc, now_minute, read, wikilink, work_id_of, work_name_of, write
from ..core.taskfile import parse_criteria, parse_tasks

START, END = "<!-- l-map:start -->", "<!-- l-map:end -->"

# (folder key, role, template, command)
FOLDER_ROLES: list[tuple[str, str, str, str]] = [
    ("templates", "사람이 정한 글 구조 (양식)", "—", "/l-template"),
    ("ideas", "떠오른 생각. 아직 작업이 아님", "아이디어", "/l-idea"),
    (
        "works",
        "기능 · 변경 하나 = 폴더 하나. 일하는 동안 고치는 곳은 여기뿐",
        "기획 · 설계 · 할 일 · 기록",
        "/l-plan → /l-design → /l-task → /l-build",
    ),
    ("current", "지금 시스템의 모습. 작업이 끝날 때만 갱신", "프로젝트 정의서 외", "/l-build (반영) · /l-sync"),
    ("ops", "회고 · 보고 · 회의록", "회의록", "/l-report"),
    ("legacy", "(브라운필드) 기존 문서 원본 보관. 고치지 않음", "기존 문서 지도", "/l-init · /l-template migrate"),
    ("debt", "이해 부채 장부. 카드 1장 = 부채 1개", "부채 카드", "/l-learn"),
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
    lines: list[str] = [f"> ⚙️ 자동 생성 — `lantern map` · 기준: {now_minute()}", ""]
    # folder table
    lines += ["## 폴더", "| 폴더 | 역할 | 문서 수 | 템플릿 | 명령 |", "|---|---|---|---|---|"]
    for key, role, tmpl, cmd in FOLDER_ROLES:
        folder = project.folder(key)
        if not folder.exists():
            continue
        count = len(_md_files(folder, recursive=True))
        lines.append(f"| {project.names.folder(key)} | {role} | {count} | {tmpl} | `{cmd}` |")
    lines.append("")

    # current state
    current = project.folder("current")
    if current.exists():
        lines += ["## 📘 현재 상태 — 시스템이 지금 어떤 모습인가"]
        for p in _md_files(current, recursive=True):
            st = _status_of(p)
            inactive = project.enums.value("current_status", "inactive")
            mark = " " + project.enums.label("current_status", "inactive") if st == inactive else ""
            lines.append(f"- {wikilink(project, p, nfc(p.stem))}{mark}")
        lines.append("")

    # works — view by stage
    works = project.work_dirs()
    lines += ["## 📦 진행 중 작업 — 단계별 보기"]
    if not works:
        lines.append("- (아직 없음 — `/l-plan`으로 시작)")
    else:
        lines += ["| 작업 | 단계 | 📋 기획 | 📐 설계 | ✅ 할 일 | 🔨 기록 |", "|---|---|---|---|---|---|"]
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
                    extra = " ✅ 승인" if approved else " ⏳ 승인 대기"
                cells.append(wikilink(project, p, p.stem, table=True) + extra)
            lines.append(f"| {wid} {name} | {project.enums['work_status'].labelled(stage) if stage else ''} | " + " | ".join(cells) + " |")
    lines.append("")

    archive = project.work_dirs(include_archive=True)
    done = [w for w in archive if w not in works]
    if done:
        lines += ["## 🗄 보관된 작업"]
        for w in done:
            lines.append(f"- {wikilink(project, project.doc_path(w, 'plan'), work_id_of(w) + ' ' + work_name_of(w))}")
        lines.append("")

    # ideas
    ideas = _md_files(project.folder("ideas"))
    if ideas:
        lines += ["## 💡 아이디어", "| 아이디어 | 유형 | 상태 |", "|---|---|---|"]
        for p in ideas:
            meta = frontmatter.parse(read(p)).meta
            lines.append(f"| {wikilink(project, p, nfc(p.stem), table=True)} | {meta.get('kind', '')} | {meta.get('status', '')} |")
        lines.append("")

    # decisions
    adrs = [p for p in _md_files(project.folder("rules")) if nfc(p.name).startswith("ADR-")]
    if adrs:
        lines += ["## 📝 결정 기록"]
        for p in adrs:
            lines.append(f"- {wikilink(project, p, nfc(p.stem))} — {_status_of(p)}")
        lines.append("")

    # debt + reports
    extras = []
    status = project.folder("debt") / project.names.file("debt_status")
    if status.exists():
        extras.append(f"- 📒 {wikilink(project, status, '부채 현황')}")
    report = project.folder("reports") / project.names.file("report")
    if report.exists():
        extras.append(f"- 📊 {wikilink(project, report, '현황 보고')}")
    legacy_map = project.folder("legacy") / project.names.file("legacy_map")
    if legacy_map.exists():
        extras.append(f"- 🗂 {wikilink(project, legacy_map, '기존 문서 지도')}")
    if extras:
        lines += ["## 바로 가기", *extras, ""]

    lines += [
        "## 명령",
        "| 하고 싶은 것 | 명령 |",
        "|---|---|",
        "| 생각 기록 | `/l-idea` |",
        "| 기획 → 설계 → 할 일 → 구현 | `/l-plan` → `/l-design` → `/l-task` → `/l-build` |",
        "| 모르는 기술 | `/l-learn` |",
        "| 현황 보기 | `/l-report` |",
        "| 새 양식 · 양식 다듬기 | `/l-template` |",
        "| 양식 검사 | `/l-check` |",
        "| 문서 ↔ 코드 맞추기 | `/l-sync` |",
        "| 중요한 결정 | `/l-adr` |",
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
    return "\n".join(l for l in block.split("\n") if not l.startswith("> ⚙️ 자동 생성"))
