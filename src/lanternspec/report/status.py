"""지금 상황 3줄 (H-4): 진행 중 작업 · 다음 할 일 · 열린 ❓ 확인 필요."""

from __future__ import annotations

from ..core import frontmatter
from ..core.project import Project, read, work_id_of, work_name_of
from ..core.taskfile import parse_tasks
from ..work.tasks import next_task

UNKNOWN = "❓ 확인 필요"


def open_unknowns(project: Project) -> list[tuple[str, int]]:
    """(doc, count) in docs still in use: active works and current state."""
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
            if UNKNOWN in l and "[!guide]" not in l and f"`{UNKNOWN}" not in l and not l.lstrip().startswith("> -")
        ]
        if lines:
            out.append((project.docs_rel(p), len(lines)))
    return out


def lines(project: Project) -> list[str]:
    works = project.work_dirs()
    if works:
        parts = []
        for w in works[:3]:
            meta = frontmatter.parse(read(w / "기획.md")).meta if (w / "기획.md").exists() else {}
            stage = str(meta.get("status") or "")
            extra = ""
            tf = w / "할 일.md"
            if tf.exists():
                ts = parse_tasks(read(tf))
                if ts:
                    extra = f", 할 일 {sum(t.done for t in ts)}/{len(ts)}"
            design = w / "설계.md"
            if (
                design.exists()
                and not frontmatter.parse(read(design)).meta.get("approved")
                and stage == project.enums.value("work_status", "design")
            ):
                extra += ", ⏳ 설계 승인 대기"
            parts.append(f"{work_id_of(w)} {work_name_of(w)} ({stage}{extra})")
        more = f" 외 {len(works) - 3}개" if len(works) > 3 else ""
        first = "📦 진행 중: " + " · ".join(parts) + more
    else:
        first = "📦 진행 중: 없음 — /l-idea 또는 /l-plan으로 시작"
    nxt = next_task(project) if works else None
    if nxt and nxt.task:
        second = f"▶ 다음 할 일: {nxt.task.id} {nxt.task.title}" + (f" [{nxt.task.size}]" if nxt.task.size else "")
    elif nxt and nxt.all_done:
        second = "▶ 다음 할 일: 모든 할 일 완료 — 현재 상태 반영(/l-build 마무리)"
    elif nxt and nxt.skipped:
        tid, why = nxt.skipped[0]
        second = f"▶ 다음 할 일: 지금 시작할 수 있는 할 일 없음 ({tid}: {why})"
    else:
        second = "▶ 다음 할 일: 없음"
    unknowns = open_unknowns(project)
    if unknowns:
        total = sum(n for _, n in unknowns)
        where = ", ".join(f"{d} ({n})" for d, n in unknowns[:3])
        third = f"❓ 확인 필요 {total}개: {where}"
    else:
        third = "❓ 확인 필요: 없음"
    return [first, second, third]
