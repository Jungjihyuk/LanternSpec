"""propose · write — learning-note drafts wait in `📒 부채/노트 초안/` until a person approves.

Not here:
    - writing into the store itself → each adapter's write (learn/knowledge/obsidian.py · notion.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core import frontmatter
from ...core.project import Project, read, safe_name, today, write
from . import KnowledgeError, adapter_for

DRAFT_SKELETON = """# {title}

> [!abstract] 한 줄 요약
> {{{{한 줄 요약}}}}

## 무엇인가

## 왜 쓰나

## 어떻게 동작하나

## 이 프로젝트에서는
"""


def propose(project: Project, title: str, content: str | None = None, area: str = "", target: str = "") -> dict:
    """Create a learning-note draft waiting for approval (in our own folder, not the store).

    Args:
        project: The project.
        title: The note's title.
        content: The note's text; a skeleton with headings when empty.
        area: Topic, kept as a tag.
        target: Where the note should go in the store; under `knowledge.areas_from` when empty.

    Returns:
        draft (path), status, target and write_mode (`knowledge.write`).

    Raises:
        KnowledgeError: A draft with that title already exists.

    Example:
        >>> propose(project, "JWT")["draft"]  # doctest: +SKIP
        'docs/📒 부채/노트 초안/JWT.md'
    """
    folder = project.folder("note_drafts")
    dest = folder / f"{safe_name(title)}.md"
    if dest.exists():
        raise KnowledgeError(f"이미 초안이 있습니다: {project.rel(dest)}")
    k = project.profile.knowledge or {}
    if not target:
        base = str(k.get("areas_from") or "").strip("/")
        target = f"{base}/{safe_name(title)}.md" if base else f"{safe_name(title)}.md"
    meta = {
        "id": f"NOTE-{safe_name(title)}",
        "type": "note-draft",
        "status": project.enums.value("note_draft_status", "pending"),
        "created": today(),
        "updated": today(),
        "area": area,
        "target": target,
    }
    body = content if content and content.strip() else DRAFT_SKELETON.format(title=safe_name(title))
    write(dest, frontmatter.render(meta, "\n" + body.lstrip("\n")))
    return {
        "draft": project.rel(dest),
        "status": project.enums.value("note_draft_status", "pending"),
        "target": target,
        "write_mode": k.get("write", "direct"),
    }


def write_draft(project: Project, draft: Path, target: str | None = None) -> dict:
    """Write an approved draft into the knowledge store and mark the draft applied.

    Args:
        project: The project.
        draft: The draft file.
        target: Where to write in the store; the draft's `target` when None.

    Returns:
        path (where it was written) and store (the store root).

    Raises:
        KnowledgeError: No store is set up, the store is propose_only, the draft is missing,
            it still has blanks, or the store refused the write.

    Example:
        >>> write_draft(project, project.folder("note_drafts") / "JWT.md")["path"]  # doctest: +SKIP
        'JWT.md'
    """
    k = project.profile.knowledge
    if not k:
        raise KnowledgeError("지식 저장소가 설정되지 않았습니다")
    if k.get("write") == "propose_only":
        raise KnowledgeError("이 저장소는 propose_only — 초안 파일만 만들고, 넣는 것은 사용자가 합니다")
    if not draft.exists():
        raise KnowledgeError(f"초안이 없습니다: {draft}")
    doc = frontmatter.parse(read(draft))
    if "{{" in doc.body:
        raise KnowledgeError("초안에 빈칸 {{…}}이 남아 있습니다 — 채운 뒤 쓰세요")
    rel = target or str(doc.meta.get("target") or draft.name)
    adapter = adapter_for(project)
    note_meta: dict[str, Any] = {"created": today()}
    if doc.meta.get("area"):
        note_meta["tags"] = [str(doc.meta["area"])]
    written = adapter.write(rel, frontmatter.render(note_meta, doc.body))
    write(
        draft, frontmatter.set_fields(read(draft), {"status": project.enums.value("note_draft_status", "applied"), "written_to": written})
    )
    return {"path": written, "store": str(Path(str(k["path"])).expanduser())}
