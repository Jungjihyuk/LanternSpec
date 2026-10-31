"""References commands: ref (list · check · index · read)."""

from __future__ import annotations

import argparse

from ..core import outline
from ..core.messages import msg
from ..core.project import Project, read
from ..refs import index as index_mod
from ..refs import sources as src_mod
from .common import Add, CliError, _p

READ_MAX_LINES = 300  # a longer section shows its sub-sections to pick from instead


def cmd_ref(a: argparse.Namespace) -> int:
    """`lantern ref [list|check|index|read]` — references: what is listed · structure · index · read one section."""
    project = _p()
    if a.action in (None, "list"):
        return _list(project)
    if not a.arg:
        raise CliError(msg("lantern ref {action} needs a path or an address", action=a.action))
    if a.action == "check":
        return _check(project, a.arg)
    if a.action == "index":
        if not a.path:
            raise CliError(msg("lantern ref index <rules|terms|domain> <path>"))
        return _index(project, a.arg, a.path)
    return _read(project, a.arg)


def _list(project: Project) -> int:
    """Print every reference with its documents and whether its index is up to date."""
    found = src_mod.sources(project)
    if not found:
        print(msg("No references yet — bring company rules · terms · domain knowledge in with /l-ref"))
        return 0
    behind = {s.document.path for s in index_mod.stale(project)}
    for s in found:
        where = msg("outside") if s.outside else msg("inside")
        if not s.path.exists():
            print(f"✖ {s.kind}  {s.entry}  ({where}) · " + msg("doesn't exist"))
            continue
        docs = src_mod.documents(project, s)
        late = sum(1 for d in docs if d.path in behind)
        state = msg("{count} not indexed or changed", count=late) if late else msg("indexed")
        print(f"{'⚠' if late else '✔'} {s.kind}  {s.entry}  ({where}) · " + msg("{count} documents", count=len(docs)) + f" · {state}")
    return 0


def _check(project: Project, path: str) -> int:
    """Print the structure problems of a file or folder (it needn't be a reference yet)."""
    found = src_mod.resolve(project, path)
    if found is None or not found.path.exists():
        raise CliError(msg("{path} doesn't exist", path=path))
    docs = src_mod.documents(project, found)
    if not docs:
        raise CliError(msg("{path} holds no Markdown document — convert PDF · HWP to .md first (keep the original)", path=path))
    bad = 0
    for d in docs:
        text = read(d.path)
        problems = outline.problems(text)
        if problems:
            bad += 1
            print(f"⚠ {d.shown}")
            print("\n".join(f"  - {p}" for p in problems))
        else:
            print(f"✔ {d.shown} · " + msg("{count} sections", count=len(outline.sections(text))))
    return 1 if bad else 0


def _index(project: Project, kind: str, path: str) -> int:
    """Index one source and say which sections are new · changed · gone (the skill tags only those)."""
    r = index_mod.index(project, kind, path)
    if r.registered and r.source.outside:
        print(
            msg(
                "✔ Listed in {file} (outside material stays out of git): {kind} {path}",
                file=project.rel(index_mod.index_file(project, True)),
                kind=kind,
                path=path,
            )
        )
    elif r.registered:
        print(msg("✔ Added to lantern.yaml references.{kind}: {path}", kind=kind, path=path))
    if r.moved:
        print(msg("✔ Taken out of lantern.yaml, which goes into git: references.{kind} {path}", kind=kind, path=path))
    print(
        msg(
            "✔ {kind} {path}: {docs} documents · {sections} sections (new {added} · changed {changed} · gone {removed})",
            kind=kind,
            path=path,
            docs=r.documents,
            sections=r.sections,
            added=len(r.added),
            changed=len(r.changed),
            removed=len(r.removed),
        )
    )
    for mark, items in (("+", r.added), ("~", r.changed), ("-", r.removed)):
        for item in items:
            print(f"  {mark} {item}")
    return 0


def _read(project: Project, address: str) -> int:
    """Print one section (or a whole document) of a reference; a long one lists its parts to read instead."""
    doc, section = src_mod.locate(project, address)
    text = read(doc.path)
    body = (outline.cut(text, section) if section else text).rstrip("\n")
    print(f"<!-- {doc.name}{' › ' + section.address if section else ''} ({doc.label}) -->")
    if index_mod.changed_since_indexed(project, doc, section):
        print(msg("⚠ Changed since it was indexed (or never indexed) — the index may be behind: /l-ref {kind}", kind=doc.source.kind))
    parts = _parts(text, section)
    if body.count("\n") + 1 > READ_MAX_LINES and parts:
        print(msg("{count} lines — read one part:", count=body.count("\n") + 1))
        for s in parts:
            print(f'  lantern ref read "{doc.name}#{s.address}"  ' + msg("({count} lines)", count=s.end - s.start))
        return 0
    print(body)
    return 0


def _parts(text: str, section: outline.Section | None) -> list[outline.Section]:
    """The sections right below a section (or the top-level sections of a whole document)."""
    inner = [s for s in outline.sections(text) if section is None or section.start < s.start < section.end]
    top = min((s.level for s in inner), default=0)
    return [s for s in inner if s.level == top]


def register(add: Add) -> None:
    """Register the references commands."""
    p = add("ref", cmd_ref, msg("References (company rules · terms · domain knowledge): list · check · index · read"))
    p.add_argument("action", nargs="?", choices=["list", "check", "index", "read"])
    p.add_argument("arg", nargs="?", help=msg("check: a file or folder · index: rules | terms | domain · read: document#section"))
    p.add_argument("path", nargs="?", help=msg("index: the file or folder to index (relative = inside, ~/… = outside)"))
