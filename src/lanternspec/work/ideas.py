"""Idea cards: find overlapping ideas, move an idea through its status flow.

Not here:
    - creating an idea card → work/scaffold.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core import frontmatter, sections
from ..core.project import Project, nfc, read, today, wikilink, write


def _tokens(s: str) -> set:
    words = re.findall(r"[\w가-힣]+", nfc(s).lower())
    out = set(w for w in words if len(w) >= 2)
    # Korean compounds: also index 2-char shingles so "카톡로그인" meets "카카오 로그인"
    for w in words:
        if re.search(r"[가-힣]", w) and len(w) >= 3:
            out |= {w[i : i + 2] for i in range(len(w) - 1)}
    return out


def idea_find(project: Project, text: str, limit: int = 5) -> list[dict[str, Any]]:
    """Find idea cards that overlap with a text, best match first.

    Words of the title and the at-a-glance line weigh three times the words of the raw note.
    Korean words are also split into two-letter pieces so compounds meet their spaced forms.

    Args:
        project: The project.
        text: The new idea, in any words.
        limit: Most results to return.

    Returns:
        One mapping per hit with id, title, status, kind, dropped_reason, path and score.

    Example:
        >>> [h["id"] for h in idea_find(project, "카톡 로그인")]  # doctest: +SKIP
        ['IDEA-003']
    """
    folder = project.folder("ideas")
    if not folder.exists():
        return []
    q = _tokens(text)
    hits = []
    for p in sorted(folder.glob("*.md")):
        body = read(p)
        doc = frontmatter.parse(body)
        title = nfc(p.stem).split(" ", 1)[-1]
        glance = re.search(r"\[!abstract\][^\n]*\n>\s*(.+)", doc.body)
        hay = _tokens(title) | _tokens(glance.group(1) if glance else "")
        hay_raw = _tokens(sections.body(doc.body, project.names.titles("raw")))
        score = 3 * len(q & hay) + len(q & hay_raw)
        if score:
            hits.append(
                {
                    "id": str(doc.meta.get("id", "")),
                    "title": title,
                    "status": doc.meta.get("status"),
                    "kind": doc.meta.get("kind"),
                    "dropped_reason": doc.meta.get("dropped_reason") or "",
                    "path": project.rel(p),
                    "score": score,
                }
            )
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits[:limit]


def idea_status(
    project: Project, idea_id: str, status: str, work: str | None = None, reason: str | None = None, note: str | None = None
) -> Path:
    """Move an idea to another status and log the change under `## 상태 기록`.

    Dropping needs a reason; marking it worked needs the work ID, and links the work's plan.

    Args:
        project: The project.
        idea_id: The idea, e.g. "IDEA-003".
        status: An idea_status value from enums.yaml.
        work: The work it became (required for the "worked" role).
        reason: Why it was dropped (required for the "dropped" role).
        note: An extra note for the log line.

    Returns:
        The idea card.

    Raises:
        ValueError: The idea or work does not exist, the status is unknown, or a required value is missing.

    Example:
        >>> idea_status(project, "IDEA-003", "작업됨", work="W-012").name  # doctest: +SKIP
        'IDEA-003 카톡 로그인.md'
    """
    path = project.find_by_id(idea_id)
    if path is None or nfc(path.parent.name) != nfc(project.folder("ideas").name):
        raise ValueError(f"아이디어 {idea_id}를 찾지 못했습니다")
    enums = project.enums
    allowed = enums.values("idea_status")
    if status not in allowed:
        raise ValueError(f"상태 '{status}'는 아이디어 상태가 아닙니다 (가능: {', '.join(allowed)})")
    roles = project.enums["idea_status"]
    if status == roles.value("dropped") and not (reason or "").strip():
        raise ValueError("버림에는 이유 한 줄이 필요합니다 (--reason)")
    text = read(path)
    meta = frontmatter.parse(text).meta
    updates: dict[str, Any] = {"status": status}
    detail = ""
    if status == roles.value("worked"):
        if not work:
            raise ValueError("작업됨에는 작업 ID가 필요합니다 (--work W-012)")
        folder = project.find_work(work)
        if folder is None:
            raise ValueError(f"작업 {work}를 찾지 못했습니다")
        link = wikilink(project, project.doc_path(folder, "plan"), work.upper())
        links = frontmatter.as_list(meta.get("links"))
        if link not in links:
            updates["links"] = links + [link]
        detail = f" → {link}"
    if status == roles.value("dropped"):
        updates["dropped_reason"] = reason
        detail = f" — {reason}"
    if note:
        detail += f" ({note})"
    icon = enums["idea_status"].icon(status)
    text = frontmatter.set_fields(text, updates)
    if not project.names.is_unused("status_log"):  # a missing section only loses the log line; check asks about it
        text = sections.append(text, project.names.titles("status_log"), f"- {today()} {icon} {status}{detail}") or text
    write(path, text)
    return path
