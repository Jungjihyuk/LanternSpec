"""Find and resolve links the way Obsidian does: path from vault root, relative path, or unique basename."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from .project import nfc

WIKI_RE = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
MD_RE = re.compile(r"(!?)\[([^\[\]\n]*)\]\(([^()\s]+(?:\([^()]*\))?[^()\s]*)\)")
INLINE_CODE = re.compile(r"`[^`\n]*`")


@dataclass
class Link:
    target: str
    line_no: int  # 1-based
    embed: bool
    kind: str  # wiki | md
    raw: str


def iter_links(text: str) -> Iterator[Link]:
    in_fence = False
    for i, line in enumerate(text.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        clean = INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)
        for m in WIKI_RE.finditer(clean):
            inner = m.group(2)
            target = re.split(r"[|#^]", inner, maxsplit=1)[0].strip().rstrip("\\").strip()
            if "{{" in inner or "${" in inner:
                continue
            yield Link(target=target, line_no=i, embed=bool(m.group(1)), kind="wiki", raw=m.group(0))
        for m in MD_RE.finditer(clean):
            target = m.group(3).strip()
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#") or "{{" in target:
                continue
            target = unquote(target.split("#", 1)[0])
            yield Link(target=target, line_no=i, embed=bool(m.group(1)), kind="md", raw=m.group(0))


class Resolver:
    def __init__(self, docs_root: Path) -> None:
        self.root = docs_root.resolve()
        self.by_name: dict[str, list[Path]] = {}
        self.by_rel: dict[str, Path] = {}
        if self.root.exists():
            for p in self.root.rglob("*"):
                if not p.is_file() or any(part.startswith(".") for part in p.relative_to(self.root).parts):
                    continue
                rel = nfc(str(p.relative_to(self.root))).lower()
                self.by_rel[rel] = p
                name = nfc(p.name).lower()
                self.by_name.setdefault(name, []).append(p)
                if p.suffix == ".md":
                    self.by_name.setdefault(nfc(p.stem).lower(), []).append(p)
                    self.by_rel[rel[:-3]] = p

    def resolve(self, link: Link, source: Path) -> Path | None:
        target = nfc(link.target).strip()
        if not target:
            return source  # [[#heading]] — same file
        key = target.lower().lstrip("/")
        if link.kind == "md":
            cand = (source.parent / target).resolve()
            if cand.exists():
                return cand
            if (self.root / target).exists():
                return self.root / target
            return None
        if key in self.by_rel:
            return self.by_rel[key]
        # relative to the source folder
        try:
            rel_src = nfc(str(source.parent.resolve().relative_to(self.root))).lower()
        except ValueError:
            rel_src = ""
        joined = f"{rel_src}/{key}".lstrip("/") if rel_src not in ("", ".") else key
        if joined in self.by_rel:
            return self.by_rel[joined]
        base = key.rsplit("/", 1)[-1]
        hits = self.by_name.get(base) or self.by_name.get(base + ".md")
        if hits:
            if "/" in key:
                for h in hits:
                    if nfc(str(h.relative_to(self.root))).lower().endswith(key) or nfc(str(h.relative_to(self.root))).lower().endswith(
                        key + ".md"
                    ):
                        return h
                return None
            return hits[0]
        return None
