r"""Where the references are: their paths, their documents, and one section by its address.

A relative path is inside the project and is listed in lantern.yaml `references`, for the team
(the domain-knowledge folder `📚 도메인 지식/` needs no listing — what is put there counts);
`~/…` and absolute paths are outside (an absolute path into the project still counts as inside) and
are listed in `.lantern/references.yaml`, out of git. Material outside is never opened by the AI's
own file tools — some tools ask before every read outside the working folder, and a run nobody
watches can't answer — so it reaches the AI through `lantern ref read`, which never prints where it is.

Responsibilities:
    - resolve each listed path and list its Markdown documents
    - list the domain-knowledge originals inside the project that are not Markdown (PDF · HWP · XLSX …)
    - find a document and a section from an address ("문서#제목", "문서#위#아래")

Not here:
    - reading headings and cutting sections → core/outline.py
    - the hashes that tell a change → refs/index.py
    - converting the originals → refs/convert.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core import outline
from ..core.messages import msg
from ..core.project import Project, nfc, read
from . import convert as conv

KINDS = ("rules", "terms", "domain")  # the lists under `references` (besides `exclude`)


@dataclass(frozen=True)
class Source:
    """One entry of a `references` list, resolved.

    Attributes:
        kind: "rules", "terms" or "domain".
        entry: The path as written in lantern.yaml.
        path: The resolved path (a file or a folder).
        outside: True when it is outside the project.

    Example:
        >>> Source("terms", "~/company/용어집.md", Path("/Users/me/company/용어집.md"), True).outside
        True
    """

    kind: str
    entry: str
    path: Path
    outside: bool


@dataclass(frozen=True)
class Document:
    """One Markdown document of a source.

    Attributes:
        source: The source it belongs to.
        path: The file.
        shown: How it is written for people: relative to the project inside, with `~` outside.

    Example:
        >>> src = Source("domain", "docs/법", Path("/p/docs/법"), False)
        >>> Document(src, Path("/p/docs/법/개인정보.md"), "docs/법/개인정보.md").name
        '개인정보'
        >>> far = Source("domain", "~/company", Path("/Users/me/company"), True)
        >>> Document(far, Path("/Users/me/company/법/개인정보.md"), "~/company/법/개인정보.md").label
        '법/개인정보.md'
    """

    source: Source
    path: Path
    shown: str

    @property
    def name(self) -> str:
        """The file name without `.md` — the document part of an address."""
        return self.path.stem

    @property
    def label(self) -> str:
        """How it is written for the AI: `shown` inside; outside, only the part below its source folder."""
        if not self.source.outside:
            return self.shown
        if self.path != self.source.path and self.path.is_relative_to(self.source.path):
            return self.path.relative_to(self.source.path).as_posix()
        return self.path.name


def resolve(project: Project, entry: str) -> Source | None:
    """Resolve one path written in `references` (the kind is left empty).

    Args:
        project: The project.
        entry: The path as written.

    Returns:
        The source; None for an empty entry.

    Example:
        >>> resolve(project, "~/company/용어집.md").outside  # doctest: +SKIP
        True
    """
    entry = entry.strip()
    if not entry:
        return None
    raw = Path(entry).expanduser()
    path = (raw if raw.is_absolute() else project.root / raw).resolve()
    return Source("", entry, path, not path.is_relative_to(project.root.resolve()))


def sources(project: Project) -> list[Source]:
    """List every reference path, resolved, in the order rules · terms · domain (lantern.yaml's, then `.lantern/`'s).

    The domain-knowledge folder counts as a domain source once it holds a document, listed or not.

    Args:
        project: The project.

    Returns:
        The sources, missing paths included (callers check `path.exists()`).

    Example:
        >>> [(s.kind, s.outside) for s in sources(project)]  # doctest: +SKIP
        [('rules', True), ('terms', False)]
    """
    from .index import outside_paths

    far = outside_paths(project)
    out = []
    for kind in KINDS:
        for entry in [*(project.profile.get(f"references.{kind}") or []), *far[kind]]:
            src = resolve(project, str(entry))
            if src:
                out.append(Source(kind, src.entry, src.path, src.outside))
    home = Source("domain", project.rel(project.folder("domain")), project.folder("domain").resolve(), False)
    if home.path.is_dir() and not any(s.kind == "domain" and s.path == home.path for s in out) and documents(project, home):
        out.append(home)
    return out


def shown(project: Project, path: Path) -> str:
    """Write a path for people: relative to the project inside, with `~` for the home folder outside.

    Args:
        project: The project.
        path: An absolute path.

    Returns:
        The path as text (`/` separators).

    Example:
        >>> shown(project, Path.home() / "company/용어집.md")  # doctest: +SKIP
        '~/company/용어집.md'
    """
    root = project.root.resolve()
    if path.is_relative_to(root):
        return path.relative_to(root).as_posix()
    if path.is_relative_to(Path.home()):
        return "~/" + path.relative_to(Path.home()).as_posix()
    return path.as_posix()


def documents(project: Project, source: Source) -> list[Document]:
    """List a source's Markdown documents (a folder's, recursively, without hidden or `_` folders or the generated domain MOC).

    Args:
        project: The project.
        source: The source.

    Returns:
        Sorted by path; [] when the path doesn't exist or isn't Markdown.

    Example:
        >>> [d.shown for d in documents(project, sources(project)[0])]  # doctest: +SKIP
        ['~/company/ai-rules/API.md', '~/company/ai-rules/DB.md']
    """
    p = source.path
    if p.is_file():
        files = [p] if p.suffix == ".md" else []
    elif p.is_dir():
        files = [f for f in sorted(p.rglob("*.md")) if not any(x.startswith((".", "_")) for x in f.relative_to(p).parts[:-1])]
    else:
        files = []
    moc = (project.folder("domain") / project.names.file("domain_moc")).resolve()
    return [Document(source, f, shown(project, f)) for f in files if f.resolve() != moc]


def all_documents(project: Project) -> list[Document]:
    """List the documents of every reference.

    Args:
        project: The project.

    Returns:
        Each document once (the first source that holds it wins).

    Example:
        >>> len(all_documents(project))  # doctest: +SKIP
        12
    """
    seen: dict[Path, Document] = {}
    for src in sources(project):
        for doc in documents(project, src):
            seen.setdefault(doc.path, doc)
    return list(seen.values())


def originals(project: Project) -> list[conv.Original]:
    """List the domain-knowledge originals inside the project (the domain folder and listed domain paths).

    Material outside the project is left to people: converting it would write next to files the project doesn't own.

    Args:
        project: The project.

    Returns:
        Each original once, with the state of its Markdown copy.

    Example:
        >>> [o.state for o in originals(project)]  # doctest: +SKIP
        ['new', 'done']
    """
    roots = [project.folder("domain").resolve(), *(s.path for s in sources(project) if s.kind == "domain" and not s.outside)]
    seen: dict[Path, conv.Original] = {}
    for root in roots:
        for o in conv.originals(root):
            seen.setdefault(o.path, o)
    return list(seen.values())


def pending(project: Project) -> str:
    """Say in one line which domain-knowledge originals still wait to be converted.

    Args:
        project: The project.

    Returns:
        "" when none wait; else the counts by format and the command to run.

    Example:
        >>> pending(project)  # doctest: +SKIP
        '변환 안 된 원본 40개 (PDF 24 · HWP 15 · DOCX 1) — lantern ref convert'
    """
    waiting = [o for o in originals(project) if o.state in ("new", "changed")]
    if not waiting:
        return ""
    counts: dict[str, int] = {}
    for o in waiting:
        counts[o.label] = counts.get(o.label, 0) + 1
    kinds = " · ".join(f"{k} {n}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    return msg("{count} originals not converted yet ({kinds}) — lantern ref convert", count=len(waiting), kinds=kinds)


def find_document(project: Project, name: str) -> Document:
    """Find a reference document by its name (file name without `.md`) or its path.

    Args:
        project: The project.
        name: "개인정보", "법/개인정보" or "docs/법/개인정보.md".

    Returns:
        The document.

    Raises:
        LookupError: No document or several match; the message lists what there is.

    Example:
        >>> find_document(project, "개인정보").shown  # doctest: +SKIP
        'docs/📚 도메인 지식/개인정보.md'
    """
    want = nfc(name.strip()).removesuffix(".md")
    docs = all_documents(project)
    if conv.kind_of(Path(want)) != "unknown" and not any(nfc(d.name) == want for d in docs):
        # an original's name ("법.pdf") stands for its Markdown copy ("법")
        stem = want[: -len(Path(want).suffix)]
        if not any(nfc(d.name) == Path(stem).name for d in docs):
            raise LookupError(msg("{name} is an original that is not converted yet — lantern ref convert, then read its copy", name=name))
        want = stem
    hits = [
        d
        for d in docs
        if nfc(d.name) == want
        or any(nfc(x).removesuffix(".md") == want or nfc(x).removesuffix(".md").endswith("/" + want) for x in (d.shown, d.label))
    ]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise LookupError(msg("Several reference documents are called {name}: {items}", name=name, items=", ".join(d.label for d in hits)))
    if not docs:
        raise LookupError(msg("No references yet — bring company rules · terms · domain knowledge in with /l-ref"))
    raise LookupError(
        msg("No reference document {name} — documents: {items}", name=name, items=", ".join(sorted({d.name for d in docs})[:10]))
    )


def locate(project: Project, address: str) -> tuple[Document, outline.Section | None]:
    """Find the document and the section an address points at.

    Args:
        project: The project.
        address: "문서" (the whole document), "문서#제목" or "문서#위#아래".

    Returns:
        (document, section); the section is None for a whole document.

    Raises:
        LookupError: The document or the section is not found, or the title repeats; the message
            gives close titles or the addresses to tell them apart.

    Example:
        >>> locate(project, "개인정보#보관 기간")[1].address  # doctest: +SKIP
        '개인정보 처리 지침#보관 기간'
    """
    name, _, query = address.partition("#")
    doc = find_document(project, name)
    if not query.strip():
        return doc, None
    text = read(doc.path)
    hits = outline.find(text, query)
    if len(hits) == 1:
        return doc, hits[0]
    if hits:
        raise LookupError(
            msg(
                "'{title}' appears {count} times in {doc} — add a title above it: {items}",
                title=query,
                count=len(hits),
                doc=doc.name,
                items=" · ".join(f"{doc.name}#{s.address}" for s in hits),
            )
        )
    close = outline.similar(text, query)
    hint = (
        msg("close titles: {items}", items=" · ".join(f"{doc.name}#{a}" for a in close))
        if close
        else msg("the document may have changed since it was indexed — /l-ref")
    )
    raise LookupError(msg("No section '{title}' in {doc} — {hint}", title=query, doc=doc.label, hint=hint))
