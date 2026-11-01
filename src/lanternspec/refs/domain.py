r"""Domain knowledge: an index of sections to read only when needed, and which of them a work uses.

People put documents into `📚 도메인 지식/` (or list a path outside the project); `/l-ref domain`
describes each section — what it is about (its topic, never its rule), when to read it, its key
terms, and whether its exact words must be read again before deciding. The AI finds its way through
the index (`lantern ref domain`) and reads one section at a time (`lantern ref read`), which this
module logs. `/l-plan` ties sections to a work's tasks: inside material in the plan's "참고한 도메인
지식" section, outside material only in `.lantern/` — nothing about it reaches git.

Responsibilities:
    - list the index (described sections, and documents not described yet), and write the MOC of inside material
    - log the sections read, and list today's for the note after compaction
    - tie a section to a work's tasks, and list what a work (or one task) uses

Not here:
    - storing a section's description → refs/index.py (describe)
    - finding a document and a section from an address → refs/sources.py
    - printing a section → cli/refs.py (read)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..core import frontmatter, outline, sections
from ..core.messages import msg
from ..core.project import Project, now_iso, read, today, work_id_of, write
from . import index as index_mod
from . import sources as src_mod

MOC_ID = "DOMAIN-moc"  # frontmatter id of the generated index document (the layout check finds it by this)
READS = "domain-reads.jsonl"
PICKS = "domain-picks.json"
_LINK = re.compile(r"\[\[([^\]|]+?)(?:\\?\|[^\]]*)?\]\]|`([^`#]+#[^`]+)`")
_TASK = re.compile(r"\b(?:W-\d+-)?(T\d+)\b")


@dataclass(frozen=True)
class Entry:
    """One line of the domain-knowledge index.

    Attributes:
        document: The document.
        section: The described section; None for a document none of whose sections is described yet.
        what: Its topic.
        when: When to read it.
        keys: Its key terms.
        verbatim: True when its exact words must be read again right before deciding.
        changed: True when the section changed after it was described.

    Example:
        >>> Entry(doc, None, "", "", [], False, False).address  # doctest: +SKIP
        '개인정보'
    """

    document: src_mod.Document
    section: outline.Section | None
    what: str
    when: str
    keys: list[str]
    verbatim: bool
    changed: bool

    @property
    def address(self) -> str:
        """The address to read it with: `문서#위#아래`, or the document's name."""
        return f"{self.document.name}#{self.section.address}" if self.section else self.document.name


def entries(project: Project) -> list[Entry]:
    """List the domain-knowledge index in document order, without what is left out.

    Args:
        project: The project.

    Returns:
        The described sections; a document with none described gets one entry with no section.

    Example:
        >>> [(e.address, e.verbatim) for e in entries(project)]  # doctest: +SKIP
        [('개인정보#개인정보 처리 지침#보관 기간', True)]
    """
    stores = {False: index_mod.load(project, False), True: index_mod.load(project, True)}
    skip = index_mod.excluded(project)
    out: list[Entry] = []
    for doc in src_mod.all_documents(project):
        if doc.source.kind != "domain" or index_mod.is_excluded(skip, doc, None):
            continue
        notes = (stores[doc.source.outside].get(doc.shown) or {}).get("notes") or {}
        text = read(doc.path)
        found = {s.address: s for s in outline.sections(text)}
        mine = []
        for address, n in notes.items():
            s = found.get(address)
            if s is None or not isinstance(n, dict) or index_mod.is_excluded(skip, doc, s):
                continue
            changed = n.get("hash") != outline.digest(outline.cut(text, s))
            keys = [str(k) for k in n.get("keys") or []]
            mine.append(Entry(doc, s, str(n.get("what") or ""), str(n.get("when") or ""), keys, bool(n.get("verbatim")), changed))
        mine.sort(key=lambda e: e.section.start if e.section else 0)
        out += mine or [Entry(doc, None, "", "", [], False, False)]
    return out


def find(project: Project, address: str) -> Entry | None:
    """Find the index entry of an address, for the read header.

    Args:
        project: The project.
        address: "문서#절" as given to `lantern ref read`.

    Returns:
        The entry of that section; None when it isn't described.

    Example:
        >>> find(project, "개인정보#보관 기간").verbatim  # doctest: +SKIP
        True
    """
    try:
        doc, section = src_mod.locate(project, address)
    except LookupError:
        return None
    if section is None:
        return None
    return next((e for e in entries(project) if e.document.path == doc.path and e.section == section), None)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(project: Project) -> str:
    """Build the index as one table, inside and outside material together, for the AI to find its way.

    Args:
        project: The project.

    Returns:
        The table and a note on the marks; "" when there is no domain knowledge.

    Example:
        >>> print(table(project))  # doctest: +SKIP
        | 주소 | 무엇 | 언제 읽나 | 핵심 용어 | 원문 필수 |
        …
    """
    found = entries(project)
    if not found:
        return ""
    rows = [msg("| Address | What | When to read | Key terms | Verbatim |"), "|---|---|---|---|---|"]
    for e in found:
        if e.section is None:
            rows.append(f"| {_cell(e.address)} | " + msg("(not described yet — /l-ref domain)") + " | | | |")
            continue
        what = ("⚠ " if e.changed else "") + _cell(e.what)
        rows.append(f"| {_cell(e.address)} | {what} | {_cell(e.when)} | {_cell(', '.join(e.keys))} | {'✅' if e.verbatim else ''} |")
    notes = [msg("Read one section with `lantern ref read \"<address>\"` — only when the situation in 'When to read' comes up.")]
    if any(e.changed for e in found):
        notes.append(msg("⚠ = the section changed after it was described — /l-ref domain"))
    return "\n".join([*rows, "", *notes])


def moc_path(project: Project) -> Path:
    """Where the index document of inside material is written.

    Args:
        project: The project.

    Returns:
        `docs/📚 도메인 지식/도메인 지식 MOC.md`.

    Example:
        >>> moc_path(project).name  # doctest: +SKIP
        '도메인 지식 MOC.md'
    """
    return project.folder("domain") / project.names.file("domain_moc")


def _link(project: Project, e: Entry, table: bool = True) -> str:
    """An Obsidian link to the section when it lies under docs/ (shown as its address in a table), else the address."""
    if e.document.path.resolve().is_relative_to(project.docs.resolve()):
        rel = project.docs_rel(e.document.path).removesuffix(".md")
        anchor = f"#{e.section.address}" if e.section else ""
        return f"[[{rel}{anchor}\\|{_cell(e.address)}]]" if table else f"[[{rel}{anchor}]]"
    return f"`{_cell(e.address)}`" if table else f"`{e.address}`"


def write_moc(project: Project) -> Path:
    """Write the index document of the domain knowledge inside the project (outside material never goes in).

    The file is rewritten only when its rows change, so the same index gives the same file on every computer.

    Args:
        project: The project.

    Returns:
        The document.

    Example:
        >>> write_moc(project).name  # doctest: +SKIP
        '도메인 지식 MOC.md'
    """
    path = moc_path(project)
    inside = [e for e in entries(project) if not e.document.source.outside]
    rows = [msg("| Section | What | When to read | Key terms | Verbatim |"), "|---|---|---|---|---|"]
    for e in inside:
        if e.section is None:
            rows.append(f"| {_link(project, e)} | " + msg("(not described yet — /l-ref domain)") + " | | | |")
            continue
        rows.append(
            f"| {_link(project, e)} | {('⚠ ' if e.changed else '') + _cell(e.what)} | {_cell(e.when)} | "
            f"{_cell(', '.join(e.keys))} | {'✅' if e.verbatim else ''} |"
        )
    if len(rows) == 2:
        rows.append(msg("| (none yet — put documents in this folder, then /l-ref domain) | | | | |"))
    body = "\n".join(
        [
            msg("# 📚 Domain Knowledge MOC"),
            "",
            msg("> ⚙️ Generated — `lantern ref domain`. Don't edit by hand; describe sections with /l-ref domain."),
            "",
            f"> [!abstract] {project.names.marker('glance')}",
            msg(
                "> Put documents in this folder (convert PDF · HWP to .md and keep the original). The AI reads a section "
                "only when 'When to read' comes up — work picks them in the plan's '{section}'.",
                section=project.names.title("domain_refs"),
            ),
            "",
            *rows,
            "",
        ]
    )
    if path.exists() and frontmatter.parse(read(path)).body.strip() == body.strip():
        return path
    meta = {"id": MOC_ID, "type": "report", "status": project.enums.value("current_status", "active"), "generated": True}
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, frontmatter.render({**meta, "updated": today()}, body))
    return path


# --------------------------------------------------------------------------- reads


def record_read(project: Project, address: str, verbatim: bool) -> None:
    """Log one section of domain knowledge read (the program logs it, not the AI).

    Args:
        project: The project.
        address: The section's full address.
        verbatim: True when its exact words must be read again before deciding.

    Example:
        >>> record_read(project, "개인정보#개인정보 처리 지침#보관 기간", True)  # doctest: +SKIP
    """
    from ..core.state import ensure_state_dir

    ensure_state_dir(project)
    with (project.state / READS).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now_iso(), "address": address, "verbatim": verbatim}, ensure_ascii=False) + "\n")


def read_today(project: Project, limit: int = 8) -> list[tuple[str, bool]]:
    """List the sections read today, latest first, each once.

    Args:
        project: The project.
        limit: How many at most.

    Returns:
        (address, verbatim) pairs.

    Example:
        >>> read_today(project)  # doctest: +SKIP
        [('개인정보#개인정보 처리 지침#보관 기간', True)]
    """
    path = project.state / READS
    if not path.exists():
        return []
    day = today()
    seen: dict[str, bool] = {}
    for line in reversed(read(path).splitlines()):
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict) or not str(item.get("at") or "").startswith(day):
            continue
        seen.setdefault(str(item.get("address") or ""), bool(item.get("verbatim")))
        if len(seen) >= limit:
            break
    return [(a, v) for a, v in seen.items() if a]


# --------------------------------------------------------------------------- picks: which sections a work uses


@dataclass(frozen=True)
class Pick:
    """One section a work uses.

    Attributes:
        address: The section's address.
        tasks: The tasks that use it ("T03"); () for the whole work.
        note: What it is used for.
        outside: True when it is outside material (kept in `.lantern/`, not in the plan).

    Example:
        >>> Pick("개인정보#보관 기간", ("T03",), "저장 로직", False).tasks
        ('T03',)
    """

    address: str
    tasks: tuple[str, ...]
    note: str
    outside: bool


def task_ids(text: str) -> tuple[str, ...]:
    """Read task IDs written as `T03` or `W-012-T03`, as `T03`, each once.

    Args:
        text: Text holding the IDs.

    Returns:
        The IDs in the order written.

    Example:
        >>> task_ids("W-012-T03, T05 · T03")
        ('T03', 'T05')
    """
    return tuple(dict.fromkeys(m.group(1) for m in _TASK.finditer(text)))


def parse_line(line: str) -> tuple[str, tuple[str, ...], str] | None:
    r"""Read one line of the plan's "참고한 도메인 지식": its address, tasks and note.

    Args:
        line: The line.

    Returns:
        (address, tasks, note); None when the line links to no section.

    Example:
        >>> parse_line("- [[📚 도메인 지식/개인정보#지침#보관 기간]] — T03 · 저장 로직 · 📌 원문 필수")
        ('개인정보#지침#보관 기간', ('T03',), 'T03 · 저장 로직 · 📌 원문 필수')
        >>> parse_line("- `법#보관`")
        ('법#보관', (), '')
    """
    m = _LINK.search(line)
    if not m:
        return None
    target = m.group(1) or m.group(2)
    name, _, rest = target.partition("#")
    address = f"{Path(name).name}#{rest}" if rest else Path(name).name
    tail = line[m.end() :].strip().lstrip("—-").strip()
    return address, task_ids(tail), tail


def _picks_file(project: Project) -> Path:
    return project.state / PICKS


def _local_picks(project: Project) -> dict[str, list[dict]]:
    try:
        data = json.loads(read(_picks_file(project)))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _same(project: Project, a: str, b: str) -> bool:
    """Whether two addresses point at the same section (as written, or once found)."""
    if a == b:
        return True
    try:
        return src_mod.locate(project, a) == src_mod.locate(project, b)
    except LookupError:
        return False


def attach(project: Project, work: Path, address: str, tasks: list[str], note: str = "") -> Path:
    """Tie a section of domain knowledge to a work's tasks (again for the same section replaces its line).

    Inside material goes into the plan's "참고한 도메인 지식"; outside material into `.lantern/`, so its
    title stays out of git. A plan made before the section existed gets it added at its end.

    Args:
        project: The project.
        work: The work folder.
        address: "문서#절" (or a whole document).
        tasks: The tasks that use it ("T03" or "W-012-T03"); [] for the whole work.
        note: What it is used for, in a few words.

    Returns:
        The file written: the plan, or `.lantern/domain-picks.json`.

    Raises:
        LookupError: The section isn't found.
        ValueError: The document isn't domain knowledge.
        sections.SectionMissing: The plan's section was removed on purpose.

    Example:
        >>> attach(project, work, "개인정보#보관 기간", ["T03"], "저장 로직").name  # doctest: +SKIP
        '기획.md'
    """
    doc, section = src_mod.locate(project, address)
    if doc.source.kind != "domain":
        raise ValueError(msg("{doc} is not a domain-knowledge document (references.domain)", doc=doc.name))
    full = f"{doc.name}#{section.address}" if section else doc.name
    ids = task_ids(" ".join(tasks))
    if doc.source.outside:
        data = _local_picks(project)
        key = work_id_of(work)
        kept = [p for p in data.get(key) or [] if not _same(project, str(p.get("address") or ""), full)]
        data[key] = [*kept, {"address": full, "tasks": list(ids), "note": note}]
        from ..core.state import ensure_state_dir

        ensure_state_dir(project)
        _picks_file(project).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return _picks_file(project)
    entry = Entry(doc, section, "", "", [], False, False)
    known = find(project, full)
    words = [", ".join(ids) or msg("whole work"), *([note] if note else []), *([msg("📌 verbatim")] if known and known.verbatim else [])]
    line = f"- {_link(project, entry, table=False)} — " + " · ".join(words)
    plan = project.doc_path(work, "plan")
    text = read(plan)
    titles = project.names.titles("domain_refs")
    m = sections.find(text, titles)
    if m is None:
        from ..check.check_docs import semver

        if semver(frontmatter.parse(text).meta.get("template_version")) >= semver(project.names.section("domain_refs").since):
            raise sections.SectionMissing(project.names, "domain_refs", plan)
        write(plan, text.rstrip("\n") + f"\n\n## {project.names.title('domain_refs')}\n{line}\n")
        return plan
    lines = [l for l in sections.body(text, titles).split("\n") if l.strip()]
    lines = [l for l in lines if not ((p := parse_line(l)) and _same(project, p[0], full))]
    replaced = sections.replace(text, titles, "\n".join([*lines, line]))
    if replaced:
        write(plan, replaced[0])
    return plan


def picks(project: Project, work: Path, task: str = "") -> list[Pick]:
    """List the sections a work uses — for one task, those tied to it and those for the whole work.

    Args:
        project: The project.
        work: The work folder.
        task: "T03" or "W-012-T03"; "" for all.

    Returns:
        The plan's lines first, then outside material from `.lantern/`.

    Example:
        >>> [(p.address, p.tasks) for p in picks(project, work, "T03")]  # doctest: +SKIP
        [('개인정보#개인정보 처리 지침#보관 기간', ('T03',))]
    """
    out: list[Pick] = []
    plan = project.doc_path(work, "plan")
    if plan.exists():
        for line in sections.body(read(plan), project.names.titles("domain_refs")).split("\n"):
            found = parse_line(line)
            if found:
                out.append(Pick(found[0], found[1], found[2], False))
    for p in _local_picks(project).get(work_id_of(work)) or []:
        if isinstance(p, dict) and p.get("address"):
            out.append(Pick(str(p["address"]), tuple(str(t) for t in p.get("tasks") or []), str(p.get("note") or ""), True))
    want = task_ids(task)
    return [p for p in out if not want or not p.tasks or want[0] in p.tasks]
