"""Obsidian folder adapter (llm-wiki included): reads files directly, never reorganises the vault.

Also serves `knowledge.type: folder` — any folder of Markdown files.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterator
from pathlib import Path

from ...core import frontmatter
from ...core.messages import msg
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
    """A knowledge store that is a folder of Markdown files (an Obsidian vault or any folder).

    Hidden folders and tool folders (`.obsidian`, `node_modules` …) are skipped.

    Attributes:
        root: The store folder.

    Example:
        >>> ObsidianAdapter(Path("~/vault").expanduser()).search("JWT")[0].path  # doctest: +SKIP
        '개발/JWT.md'
    """

    name = "obsidian"

    def __init__(self, root: Path) -> None:
        """Open a store folder.

        Args:
            root: The store folder.

        Raises:
            KnowledgeError: The folder does not exist.
        """
        self.root = root.resolve()
        if not self.root.exists():
            raise KnowledgeError(msg("Knowledge store folder doesn't exist: {root}", root=root))

    def _files(self) -> Iterator[Path]:
        for p in self.root.rglob("*.md"):
            rel = p.relative_to(self.root)
            if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
                continue
            yield p

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        """Implement Adapter.search over file names, aliases, headings, body text and tags.

        An exact title scores most, then an alias, a title containing the term, headings, and body mentions.

        Args:
            query: The term.
            aliases: Other names for the term.
            limit: Most results to return.

        Returns:
            The best matches, best first.

        Example:
            >>> ObsidianAdapter(vault).search("JWT", ["JSON Web Token"])[0].score  # doctest: +SKIP
            180
        """
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
        r"""Implement Adapter.read for a file inside the store.

        Args:
            path: The note's path, relative to the store root.

        Returns:
            The note's text.

        Raises:
            KnowledgeError: The file does not exist or is outside the store.

        Example:
            >>> ObsidianAdapter(vault).read("개발/JWT.md")  # doctest: +SKIP
            '# JWT\n…'
        """
        p = (self.root / path).resolve()
        if self.root not in p.parents or not p.exists():
            raise KnowledgeError(msg("Note not found: {path}", path=path))
        return p.read_text(encoding="utf-8")

    def write(self, rel_path: str, content: str) -> str:
        r"""Implement Adapter.write by creating a new file inside the store.

        Args:
            rel_path: Where to create it, relative to the store root.
            content: The note's text.

        Returns:
            The created file, relative to the store root.

        Raises:
            KnowledgeError: The path is outside the store, or a file is already there.

        Example:
            >>> ObsidianAdapter(vault).write("개발/JWT.md", "# JWT\n")  # doctest: +SKIP
            '개발/JWT.md'
        """
        p = (self.root / rel_path).resolve()
        if self.root not in p.parents:
            raise KnowledgeError(msg("Can't write outside the store"))
        if p.exists():
            raise KnowledgeError(msg("A note with the same name already exists: {rel_path} (not overwritten)", rel_path=rel_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return nfc(str(p.relative_to(self.root)))

    def areas(self, folder: str) -> list[str]:
        """Implement Adapter.areas: the subfolders of a folder.

        Args:
            folder: A folder of the store.

        Returns:
            Subfolder names, sorted; empty when the folder does not exist.

        Example:
            >>> ObsidianAdapter(vault).areas("개발")  # doctest: +SKIP
            ['백엔드', '프론트']
        """
        base = self.root / folder
        if not base.is_dir():
            return []
        return sorted(nfc(p.name) for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
