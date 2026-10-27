"""Obsidian folder adapter (llm-wiki included): reads files directly, never reorganises the vault."""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterator
from pathlib import Path

from ...core import frontmatter
from ...core.project import nfc
from . import Adapter, Hit, KnowledgeError

SKIP_DIRS = {".obsidian", ".trash", ".git", "node_modules", ".smart-connections"}


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_.·/]+", "", nfc(s).lower())


def _summary(meta: dict, body: str) -> str:
    for key in ("summary", "description", "요약"):
        if meta.get(key):
            return str(meta[key])[:200]
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith("#") or p.startswith("```") or p.startswith("---") or p.startswith("!["):
            continue
        p = re.sub(r"^>\s*(\[![^\]]*\][^\n]*\n?)?", "", p).strip()
        p = re.sub(r"\s+", " ", p)
        if p:
            return p[:200]
    return ""


class ObsidianAdapter(Adapter):
    name = "obsidian"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise KnowledgeError(f"지식 저장소 폴더가 없습니다: {root}")

    def _files(self) -> Iterator[Path]:
        for p in self.root.rglob("*.md"):
            rel = p.relative_to(self.root)
            if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
                continue
            yield p

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        terms = [t for t in [query, *(aliases or [])] if t and t.strip()]
        nterms = [_norm(t) for t in terms]
        lterms = [nfc(t).lower() for t in terms]
        hits: list[Hit] = []
        for p in self._files():
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            doc = frontmatter.parse(text)
            title = nfc(p.stem)
            ntitle = _norm(title)
            note_aliases = [str(a) for a in frontmatter.as_list(doc.meta.get("aliases"))]
            score = 0
            for nt in nterms:
                if not nt:
                    continue
                if ntitle == nt:
                    score += 100
                elif nt in ntitle:
                    score += 40
                if any(_norm(a) == nt for a in note_aliases):
                    score += 80
            low = nfc(doc.body).lower()
            for lt in lterms:
                if not lt:
                    continue
                for heading in re.findall(r"^#+\s+(.+)$", low, re.M):
                    if lt in heading:
                        score += 15
                count = low.count(lt)
                score += min(count, 10) * 2
            tags = " ".join(str(t) for t in frontmatter.as_list(doc.meta.get("tags"))).lower()
            if any(lt in tags for lt in lterms):
                score += 10
            if score <= 0:
                continue
            updated = _dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
            hits.append(
                Hit(
                    title=title, path=nfc(str(p.relative_to(self.root))), summary=_summary(doc.meta, doc.body), updated=updated, score=score
                )
            )
        hits.sort(key=lambda h: (-h.score, h.path))
        return hits[:limit]

    def read(self, path: str) -> str:
        p = (self.root / path).resolve()
        if self.root not in p.parents or not p.exists():
            raise KnowledgeError(f"노트를 찾지 못했습니다: {path}")
        return p.read_text(encoding="utf-8")

    def write(self, rel_path: str, content: str) -> str:
        p = (self.root / rel_path).resolve()
        if self.root not in p.parents:
            raise KnowledgeError("저장소 밖에는 쓸 수 없습니다")
        if p.exists():
            raise KnowledgeError(f"이미 같은 이름의 노트가 있습니다: {rel_path} (덮어쓰지 않음)")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return nfc(str(p.relative_to(self.root)))

    def areas(self, folder: str) -> list[str]:
        base = self.root / folder
        if not base.is_dir():
            return []
        return sorted(nfc(p.name) for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
