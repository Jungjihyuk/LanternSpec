"""Idea cards: find overlapping ideas, move an idea through its status flow.

Not here:
    - creating an idea card → work/scaffold.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core import frontmatter, sections
from ..core.messages import msg
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
        One mapping per hit with id, title, status, kind, dropped_reason, blocked_reason, revisit_when, path and score.

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
                    "blocked_reason": doc.meta.get("blocked_reason") or "",
                    "revisit_when": doc.meta.get("revisit_when") or "",
                    "path": project.rel(p),
                    "score": score,
                }
            )
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return hits[:limit]


def idea_path(project: Project, idea_id: str) -> Path | None:
    """Find an idea card by its ID.

    Args:
        project: The project.
        idea_id: The ID, e.g. "IDEA-003".

    Returns:
        The card; None when nothing in the ideas folder has that ID.

    Example:
        >>> idea_path(project, "IDEA-003").name  # doctest: +SKIP
        'IDEA-003 카톡 로그인.md'
    """
    path = project.find_by_id(idea_id)
    return path if path is not None and nfc(path.parent.name) == nfc(project.folder("ideas").name) else None


def _log(project: Project, text: str, line: str) -> str:
    """Add a line to the status log; a missing section only loses the line, and check asks about it."""
    if project.names.is_unused("status_log"):
        return text
    return sections.append(text, project.names.titles("status_log"), line) or text


def link_card(project: Project, path: Path, link: str, line: str) -> None:
    """Link a card made because of an idea from that idea, and log it.

    Args:
        project: The project.
        path: The idea card.
        link: The wikilink of the new card.
        line: The line for the status log.

    Example:
        >>> link_card(project, path, "[[D-009]]", "- 2026-11-03 → [[D-009]]")  # doctest: +SKIP
    """
    text = read(path)
    links = frontmatter.as_list(frontmatter.parse(text).meta.get("links"))
    write(path, _log(project, frontmatter.set_fields(text, {"links": [*links, link]}), line))


def idea_status(
    project: Project,
    idea_id: str,
    status: str,
    work: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    revisit: str | None = None,
) -> Path:
    """Move an idea to another status and log the change under `## 상태 기록`.

    Dropping needs a reason; marking it worked needs the work ID, and links the work's plan. Blocking
    needs why and what would reopen it; leaving the blocked status clears both, and the log keeps them.

    Args:
        project: The project.
        idea_id: The idea, e.g. "IDEA-003".
        status: An idea_status value from enums.yaml.
        work: The work it became (required for the "worked" role).
        reason: Why it was dropped or blocked (required for the "dropped" and "blocked" roles).
        note: An extra note for the log line.
        revisit: What would reopen it, in checkable terms (required for the "blocked" role).

    Returns:
        The idea card.

    Raises:
        ValueError: The idea or work does not exist, the status is unknown, or a required value is missing.

    Example:
        >>> idea_status(project, "IDEA-003", "작업됨", work="W-012").name  # doctest: +SKIP
        'IDEA-003 카톡 로그인.md'
    """
    path = idea_path(project, idea_id)
    if path is None:
        raise ValueError(msg("Idea {idea_id} not found", idea_id=idea_id))
    enums = project.enums
    allowed = enums.values("idea_status")
    if status not in allowed:
        raise ValueError(msg("'{status}' is not an idea status (available: {items})", status=status, items=", ".join(allowed)))
    roles = project.enums["idea_status"]
    if status == roles.value("dropped") and not (reason or "").strip():
        raise ValueError(msg("Dropping needs a one-line reason (--reason)"))
    blocked = status == roles.roles.get("blocked")  # a project not upgraded yet has no such value
    if blocked and not ((reason or "").strip() and (revisit or "").strip()):
        raise ValueError(msg("Blocking needs why (--reason) and what would reopen it (--revisit)"))
    text = read(path)
    meta = frontmatter.parse(text).meta
    updates: dict[str, Any] = {"status": status}
    detail = ""
    if status == roles.value("worked"):
        if not work:
            raise ValueError(msg("In-work needs a work ID (--work W-012)"))
        folder = project.find_work(work)
        if folder is None:
            raise ValueError(msg("Work {work} not found", work=work))
        link = wikilink(project, project.doc_path(folder, "plan"), work.upper())
        links = frontmatter.as_list(meta.get("links"))
        if link not in links:
            updates["links"] = links + [link]
        detail = f" → {link}"
    if status == roles.value("dropped"):
        updates["dropped_reason"] = reason
        detail = f" — {reason}"
    if blocked:
        updates |= {"blocked_reason": reason, "revisit_when": revisit}
        detail = " — " + msg("{reason} (look again when: {revisit})", reason=reason, revisit=revisit)
    elif meta.get("blocked_reason") or meta.get("revisit_when"):
        updates |= {"blocked_reason": "", "revisit_when": ""}
    if note:
        detail += f" ({note})"
    icon = enums["idea_status"].icon(status)
    write(path, _log(project, frontmatter.set_fields(text, updates), f"- {today()} {icon} {status}{detail}"))
    return path
