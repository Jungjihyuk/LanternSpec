r"""The index of the references: a hash per document and per section, to tell what changed since it was brought in.

Material inside the project is indexed in `docs/0. 템플릿/_meta/references.yaml` (committed, so the
team gets the same verdict); material outside in `.lantern/references.yaml` (never committed, so a
private document's titles don't leak into the repository). Only `lantern` writes these files.

Responsibilities:
    - index one source (and add it to lantern.yaml `references` when it isn't there yet)
    - tell which documents changed, or were never indexed, since

Not here:
    - finding the documents and sections → refs/sources.py
    - what the AI writes about each section (what · when to read · strength) → the /l-ref skill
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core import outline
from ..core import profile as profile_mod
from ..core.messages import msg
from ..core.project import Project, read
from . import sources as src_mod

FILE = "references.yaml"


@dataclass
class IndexResult:
    """What one `lantern ref index` run found.

    Attributes:
        source: The indexed source.
        documents: How many documents it holds.
        sections: How many sections they hold.
        added: Sections new since the last run ("문서#제목").
        changed: Sections whose text changed.
        removed: Sections gone.
        registered: True when the path was just added to lantern.yaml.

    Example:
        >>> IndexResult(src_mod.Source("terms", "용어집.md", Path("용어집.md"), False), 1, 3).changed
        []
    """

    source: src_mod.Source
    documents: int
    sections: int
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    registered: bool = False


def index_file(project: Project, outside: bool) -> Path:
    """Where the index of inside or outside material is kept.

    Args:
        project: The project.
        outside: True for material outside the project.

    Returns:
        `.lantern/references.yaml` for outside, `docs/0. 템플릿/_meta/references.yaml` for inside.

    Example:
        >>> index_file(project, True).as_posix().endswith(".lantern/references.yaml")  # doctest: +SKIP
        True
    """
    return project.state / FILE if outside else project.templates_dir / "_meta" / FILE


def load(project: Project, outside: bool) -> dict[str, Any]:
    """Read one index.

    Args:
        project: The project.
        outside: Which index.

    Returns:
        Document (as shown) → {kind, hash, sections: {address: hash}}; {} when there is none.

    Example:
        >>> load(project, False)["docs/3. 현재 상태/규칙/용어집.md"]["kind"]  # doctest: +SKIP
        'terms'
    """
    path = index_file(project, outside)
    data = yaml.safe_load(read(path)) if path.exists() else None
    return dict((data or {}).get("documents") or {})


def _save(project: Project, outside: bool, docs: dict[str, Any]) -> None:
    path = index_file(project, outside)
    if outside:
        from ..core.state import ensure_state_dir

        ensure_state_dir(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "# " + msg("Written by lantern ref index — don't edit by hand") + "\n"
    body = yaml.safe_dump({"documents": dict(sorted(docs.items()))}, allow_unicode=True, sort_keys=False)
    path.write_text(head + body, encoding="utf-8")


def entry_for(doc: src_mod.Document) -> dict[str, Any]:
    """Hash one document and each of its sections.

    Args:
        doc: The document.

    Returns:
        {kind, hash, sections: {address: hash}}; a repeated address keeps its first section.

    Example:
        >>> entry_for(doc)["sections"]  # doctest: +SKIP
        {'개인정보#보관 기간': '9f2c…'}
    """
    text = read(doc.path)
    hashes: dict[str, str] = {}
    for s in outline.sections(text):
        hashes.setdefault(s.address, outline.digest(outline.cut(text, s)))
    return {"kind": doc.source.kind, "hash": outline.digest(text), "sections": hashes}


def index(project: Project, kind: str, entry: str) -> IndexResult:
    """Index one source, and add it to lantern.yaml `references.<kind>` when it isn't listed yet.

    Args:
        project: The project.
        kind: "rules", "terms" or "domain".
        entry: The path as the person gave it (relative = inside, `~/…` or absolute = outside).

    Returns:
        What was found, with the sections new · changed · gone since the last run.

    Raises:
        ValueError: An unknown kind, or a path that doesn't exist or holds no Markdown.

    Example:
        >>> index(project, "terms", "~/company/용어집.md").sections  # doctest: +SKIP
        14
    """
    if kind not in src_mod.KINDS:
        raise ValueError(msg("Unknown kind {kind} — one of {items}", kind=kind, items=", ".join(src_mod.KINDS)))
    found = src_mod.resolve(project, entry)
    if found is None or not found.path.exists():
        raise ValueError(msg("{path} doesn't exist", path=entry))
    source = src_mod.Source(kind, found.entry, found.path, found.outside)
    docs = src_mod.documents(project, source)
    if not docs:
        raise ValueError(msg("{path} holds no Markdown document — convert PDF · HWP to .md first (keep the original)", path=entry))
    listed = [str(x) for x in project.profile.get(f"references.{kind}") or []]
    registered = not any((r := src_mod.resolve(project, x)) and r.path == source.path for x in listed)
    if registered:
        profile_mod.update(project.root, {f"references.{kind}": [*listed, entry]})
        project.profile = profile_mod.load(project.root)
    stored = load(project, source.outside)
    prefix = src_mod.shown(project, source.path)
    old = {k: v for k, v in stored.items() if k == prefix or k.startswith(prefix.rstrip("/") + "/")}
    result = IndexResult(source, len(docs), 0, registered=registered)
    for doc in docs:
        new = entry_for(doc)
        before = (old.pop(doc.shown, None) or {}).get("sections") or {}
        now = new["sections"]
        result.sections += len(now)
        result.added += [f"{doc.name}#{a}" for a in now if a not in before]
        result.changed += [f"{doc.name}#{a}" for a in now if a in before and before[a] != now[a]]
        result.removed += [f"{doc.name}#{a}" for a in before if a not in now]
        stored[doc.shown] = new
    for gone, rec in old.items():  # documents no longer in the source
        result.removed += [f"{Path(gone).stem}#{a}" for a in (rec.get("sections") or {})]
        stored.pop(gone)
    _save(project, source.outside, stored)
    return result


@dataclass
class Stale:
    """A reference document whose index is behind it.

    Attributes:
        document: The document.
        changed: The sections changed or added since it was indexed; [] when it was never indexed.
        never: True when it was never indexed.

    Example:
        >>> Stale(doc, [], True).never  # doctest: +SKIP
        True
    """

    document: src_mod.Document
    changed: list[str]
    never: bool = False


def stale(project: Project) -> list[Stale]:
    """Find the reference documents that changed, or were never indexed, since the last `lantern ref index`.

    Args:
        project: The project.

    Returns:
        One entry per such document.

    Example:
        >>> [(s.document.name, s.changed) for s in stale(project)]  # doctest: +SKIP
        [('개인정보', ['개인정보 처리 지침#보관 기간'])]
    """
    stores = {False: load(project, False), True: load(project, True)}
    out = []
    for doc in src_mod.all_documents(project):
        rec = stores[doc.source.outside].get(doc.shown)
        if rec is None:
            out.append(Stale(doc, [], True))
            continue
        now = entry_for(doc)
        if now["hash"] != rec.get("hash"):
            before = rec.get("sections") or {}
            out.append(Stale(doc, [a for a, h in now["sections"].items() if before.get(a) != h]))
    return out


def changed_since_indexed(project: Project, doc: src_mod.Document, section: outline.Section | None) -> bool:
    """Tell whether a section (or a whole document) differs from what was indexed.

    Args:
        project: The project.
        doc: The document.
        section: The section; None for the whole document.

    Returns:
        True when it changed or was never indexed.

    Example:
        >>> changed_since_indexed(project, doc, None)  # doctest: +SKIP
        False
    """
    rec = load(project, doc.source.outside).get(doc.shown)
    if rec is None:
        return True
    text = read(doc.path)
    if section is None:
        return outline.digest(text) != rec.get("hash")
    return (rec.get("sections") or {}).get(section.address) != outline.digest(outline.cut(text, section))
