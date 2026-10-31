r"""The index of the references: a hash per document and per section, to tell what changed since it was brought in.

Material inside the project is indexed in `docs/0. 템플릿/_meta/references.yaml` (committed, so the
team gets the same verdict); material outside in `.lantern/references.yaml` (never committed). The
outside file also holds the outside paths themselves, so nothing about private material — where it
is, its titles, its index — reaches the repository. Only `lantern` writes these files.

Responsibilities:
    - index one source, and list its path (inside → lantern.yaml `references`, outside → `.lantern/references.yaml`)
    - tell which documents changed, or were never indexed, since
    - store what the person approved for a company-rules section (scope · strength), and exclusions

Not here:
    - finding the documents and sections → refs/sources.py
    - which approved rules go where → refs/rules.py
    - proposing the scope and strength of each section → the /l-ref skill
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
        registered: True when the path was just listed (in lantern.yaml, or in `.lantern/` for outside material).
        moved: True when an outside path was taken out of lantern.yaml (which goes into git).

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
    moved: bool = False


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


def _file(project: Project, outside: bool) -> dict[str, Any]:
    path = index_file(project, outside)
    data = yaml.safe_load(read(path)) if path.exists() else None
    return data if isinstance(data, dict) else {}


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
    return dict(_file(project, outside).get("documents") or {})


def outside_paths(project: Project) -> dict[str, list[str]]:
    """Read the outside paths, kept in `.lantern/references.yaml` instead of lantern.yaml so they stay out of git.

    Args:
        project: The project.

    Returns:
        Kind → paths as written; [] for a kind with none.

    Example:
        >>> outside_paths(project)["terms"]  # doctest: +SKIP
        ['~/company/용어집.md']
    """
    listed = _file(project, True).get("sources") or {}
    return {k: [str(x) for x in listed.get(k) or []] for k in src_mod.KINDS}


def outside_exclude(project: Project) -> list[str]:
    """Read the exclusions of outside material, kept in `.lantern/references.yaml` so their titles stay out of git.

    Args:
        project: The project.

    Returns:
        Addresses ("문서#절").

    Example:
        >>> outside_exclude(project)  # doctest: +SKIP
        ['개인정보#파기']
    """
    return [str(x) for x in _file(project, True).get("exclude") or []]


def _save(project: Project, outside: bool, docs: dict[str, Any], **keep: Any) -> None:
    """Write one index; the outside one also keeps its paths and exclusions (given ones replace them)."""
    path = index_file(project, outside)
    data: dict[str, Any] = {}
    if outside:
        from ..core.state import ensure_state_dir

        ensure_state_dir(project)
        paths = keep.get("sources") or outside_paths(project)
        excluded = keep["exclude"] if "exclude" in keep else outside_exclude(project)
        data["sources"] = {k: v for k, v in paths.items() if v}
        if excluded:
            data["exclude"] = excluded
    data["documents"] = dict(sorted(docs.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "# " + msg("Written by lantern ref index — don't edit by hand") + "\n"
    path.write_text(head + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


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
    """Index one source, and list its path when it isn't listed yet.

    An inside path is listed in lantern.yaml `references.<kind>`, for the team; an outside path in
    `.lantern/references.yaml`, and taken out of lantern.yaml if someone wrote it there.

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

    def same(x: str) -> bool:
        return bool((r := src_mod.resolve(project, x)) and r.path == source.path)

    shared = [str(x) for x in project.profile.get(f"references.{kind}") or []]
    paths = outside_paths(project)
    moved = False
    if source.outside:
        registered = not any(same(x) for x in paths[kind])
        if registered:
            paths[kind].append(entry)
        moved = any(same(x) for x in shared)
        if moved:
            profile_mod.update(project.root, {f"references.{kind}": [x for x in shared if not same(x)]})
    else:
        registered = not any(same(x) for x in shared)
        if registered:
            profile_mod.update(project.root, {f"references.{kind}": [*shared, entry]})
    project.profile = profile_mod.load(project.root)
    stored = load(project, source.outside)
    prefix = src_mod.shown(project, source.path)
    old = {k: v for k, v in stored.items() if k == prefix or k.startswith(prefix.rstrip("/") + "/")}
    result = IndexResult(source, len(docs), 0, registered=registered, moved=moved)
    for doc in docs:
        new = entry_for(doc)
        rec = old.pop(doc.shown, None) or {}
        before = rec.get("sections") or {}
        now = new["sections"]
        applies = {a: tag for a, tag in (rec.get("applies") or {}).items() if a in now}  # approvals of sections still there
        if applies:
            new["applies"] = applies
        result.sections += len(now)
        result.added += [f"{doc.name}#{a}" for a in now if a not in before]
        result.changed += [f"{doc.name}#{a}" for a in now if a in before and before[a] != now[a]]
        result.removed += [f"{doc.name}#{a}" for a in before if a not in now]
        stored[doc.shown] = new
    for gone, rec in old.items():  # documents no longer in the source
        result.removed += [f"{Path(gone).stem}#{a}" for a in (rec.get("sections") or {})]
        stored.pop(gone)
    if source.outside:
        _save(project, True, stored, sources=paths)
    else:
        _save(project, False, stored)
    return result


def tag(project: Project, address: str, scope: str, strength: str) -> str:
    """Store where an approved company rule applies and how strongly; an empty scope takes the approval away.

    Args:
        project: The project.
        address: The section ("문서#절"); the document must be indexed.
        scope: "all", a part's folder or a language (see refs/rules.py `scopes`); "" to take it away.
        strength: "must" or "should".

    Returns:
        The section's full address.

    Raises:
        LookupError: The section isn't found.
        ValueError: The document isn't a company-rules document or isn't indexed, or the scope or strength is unknown.

    Example:
        >>> tag(project, "API#오류 응답", "backend", "must")  # doctest: +SKIP
        'API#API#오류 응답'
    """
    from . import rules as rules_mod

    doc, section = src_mod.locate(project, address)
    if section is None:
        raise ValueError(msg("Name a section, not a whole document: {address}#<title>", address=address))
    if doc.source.kind != "rules":
        raise ValueError(msg("{doc} is not a company-rules document (references.rules)", doc=doc.name))
    if scope and scope not in rules_mod.scopes(project):
        raise ValueError(msg("Unknown scope {scope} — one of {items}", scope=scope, items=", ".join(rules_mod.scopes(project))))
    if strength not in rules_mod.STRENGTHS:
        raise ValueError(msg("Unknown strength {strength} — must or should", strength=strength))
    stored = load(project, doc.source.outside)
    rec = stored.get(doc.shown)
    if rec is None:
        raise ValueError(msg("{doc} isn't indexed yet — lantern ref index rules <path>", doc=doc.name))
    applies = dict(rec.get("applies") or {})
    if scope:
        applies[section.address] = {"scope": scope, "strength": strength}
    else:
        applies.pop(section.address, None)
    rec["applies"] = applies
    if not applies:
        rec.pop("applies")
    _save(project, doc.source.outside, stored)
    return f"{doc.name}#{section.address}"


def exclude(project: Project, address: str, undo: bool = False) -> bool:
    """Leave a section (or a document) out of this project, or bring it back.

    The exclusion of inside material goes into lantern.yaml `references.exclude`, for the team; of
    outside material into `.lantern/references.yaml`, so its title stays out of git.

    Args:
        project: The project.
        address: "문서" or "문서#절".
        undo: True to bring it back.

    Returns:
        True when something changed.

    Raises:
        LookupError: The address isn't found.

    Example:
        >>> exclude(project, "개인정보#파기")  # doctest: +SKIP
        True
    """
    doc, _ = src_mod.locate(project, address)
    listed = outside_exclude(project) if doc.source.outside else [str(x) for x in project.profile.get("references.exclude") or []]
    now = [x for x in listed if x != address] if undo else (listed if address in listed else [*listed, address])
    if now == listed:
        return False
    if doc.source.outside:
        _save(project, True, load(project, True), exclude=now)
    else:
        profile_mod.update(project.root, {"references.exclude": now})
        project.profile = profile_mod.load(project.root)
    return True


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
