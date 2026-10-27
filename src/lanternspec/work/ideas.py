"""Idea cards (ID-01 · ID-02): find overlapping ideas, move an idea through its status flow."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core import enums as enums_mod
from ..core import frontmatter
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
        raw = re.search(r"## 원문(.*?)(?=\n## )", doc.body, re.S)
        hay_raw = _tokens(raw.group(1) if raw else "")
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


def _append_under(text: str, heading: str, line: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return text.rstrip() + f"\n\n{marker}\n{line}\n"
    head, tail = text.split(marker, 1)
    parts = tail.split("\n")
    insert_at = len(parts)
    for i, l in enumerate(parts[1:], start=1):
        if l.startswith("## ") or l.startswith("<!--"):
            insert_at = i
            break
    while insert_at > 1 and parts[insert_at - 1].strip() == "":
        insert_at -= 1
    parts.insert(insert_at, line)
    return head + marker + "\n".join(parts)


def idea_status(
    project: Project, idea_id: str, status: str, work: str | None = None, reason: str | None = None, note: str | None = None
) -> Path:
    path = project.find_by_id(idea_id)
    if path is None or nfc(path.parent.name) != nfc(project.folder("ideas").name):
        raise ValueError(f"아이디어 {idea_id}를 찾지 못했습니다")
    enums = enums_mod.load(project.enums_file)
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
        link = wikilink(project, folder / "기획.md", work.upper())
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
    write(path, _append_under(text, "상태 기록", f"- {today()} {icon} {status}{detail}"))
    return path
