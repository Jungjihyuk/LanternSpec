r"""Where the references are: the paths in lantern.yaml `references`, their documents, and one section by its address.

A relative path is inside the project; `~/…` and absolute paths are outside (an absolute path into
the project still counts as inside). Material outside is never opened by the AI's own file tools —
some tools ask before every read outside the working folder, and a run nobody watches can't answer —
so it reaches the AI through `lantern ref read`.

Responsibilities:
    - resolve each `references` entry and list its Markdown documents
    - find a document and a section from an address ("문서#제목", "문서#위#아래")

Not here:
    - reading headings and cutting sections → core/outline.py
    - the hashes that tell a change → refs/index.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core import outline
from ..core.messages import msg
from ..core.project import Project, read

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
    """

    source: Source
    path: Path
    shown: str

    @property
    def name(self) -> str:
        """The file name without `.md` — the document part of an address."""
        return self.path.stem


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
    """List every entry of lantern.yaml `references`, resolved, in the order rules · terms · domain.

    Args:
        project: The project.

    Returns:
        The sources, missing paths included (callers check `path.exists()`).

    Example:
        >>> [(s.kind, s.outside) for s in sources(project)]  # doctest: +SKIP
        [('rules', True), ('terms', False)]
    """
    out = []
    for kind in KINDS:
        for entry in project.profile.get(f"references.{kind}") or []:
            src = resolve(project, str(entry))
            if src:
                out.append(Source(kind, src.entry, src.path, src.outside))
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
    """List a source's Markdown documents (a folder's, recursively, without hidden or `_` folders).

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
    return [Document(source, f, shown(project, f)) for f in files]


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
    want = name.strip().removesuffix(".md")
    docs = all_documents(project)
    hits = [d for d in docs if d.name == want or d.shown.removesuffix(".md") == want or d.shown.removesuffix(".md").endswith("/" + want)]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise LookupError(msg("Several reference documents are called {name}: {items}", name=name, items=", ".join(d.shown for d in hits)))
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
    raise LookupError(msg("No section '{title}' in {doc} — {hint}", title=query, doc=doc.shown, hint=hint))
