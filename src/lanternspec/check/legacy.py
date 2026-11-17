"""Existing documents of a brownfield project: originals stay in `5. 기존 문서/`; the script builds the map and TODOs.

Responsibilities:
    - plan which items of the documents root move to the legacy folder and which stay, with the reason (nothing changes)
    - apply the plan: `git mv` (history continues), one commit
    - keep the legacy map's rows in step and collect TODO-like lines

Not here:
    - deciding where each document's content goes — the person does that in the map (/l-init)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import frontmatter, sections
from ..core.messages import msg
from ..core.project import Project, git, git_out, move_path, nfc, read, write

TODO_RE = re.compile(
    r"(TODO|FIXME|later|someday|to do|idea|needs? improv|나중에|추후|언젠가|해야 할|할 것|아이디어|개선 필요|- \[ \])", re.I
)
PAGES_FILES = ("index.html", "CNAME", "_config.yml")  # a documents root that GitHub Pages serves
PROSE = {".md", ".markdown", ".mdx", ".txt", ".rst"}  # a path written here is a link to fix, not a path a program reads
_TO_DOCUMENT = re.compile(r"\.(?:md|markdown|mdx)\b")  # … and so is a path that leads to a document, wherever it is written
SKIP_HOOKS = {"LANTERN_SKIP_HOOKS": "1"}  # our own git hooks would check the commit we make


class LegacyError(RuntimeError):
    """The existing documents can't be moved now; the message says why and what to do.

    Example:
        >>> str(LegacyError("변경 사항이 있습니다"))
        '변경 사항이 있습니다'
    """


@dataclass
class AdoptItem:
    """One file or folder of the documents root, and what adopt does with it.

    Attributes:
        path: The file or folder.
        move: True when it goes to the legacy folder; False when it stays.
        reason: Why, for the person.

    Example:
        >>> AdoptItem(Path("docs/updates"), False, "Scripts/release.sh가 이 경로를 씁니다").move
        False
    """

    path: Path
    move: bool
    reason: str


@dataclass
class AdoptPlan:
    """What `lantern legacy adopt` would do.

    Attributes:
        items: Every item looked at, in name order.
        links: (file outside the documents root, moved path it mentions) — links a person fixes after the move.
        notes: Warnings about the documents root as a whole (e.g. it is a GitHub Pages site).

    Example:
        >>> AdoptPlan([AdoptItem(Path("docs/old"), True, "문서"), AdoptItem(Path("docs/updates"), False, "…")]).moves
        [PosixPath('docs/old')]
    """

    items: list[AdoptItem] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def moves(self) -> list[Path]:
        """The items that move."""
        return [i.path for i in self.items if i.move]


def _our_names(project: Project) -> set[str]:
    """Names LanternSpec uses at the top of the documents root."""
    return {nfc(v.split("/")[0]) for v in project.names.folders().values()} | {nfc(project.names.file("moc"))}


def _made_by_lantern(project: Project, item: Path) -> bool:
    """Tell ours from a same-named item by a mark, not the name: the MOC by its frontmatter, folders by the installed enums.yaml."""
    if nfc(item.name) == nfc(project.names.file("moc")):
        try:
            meta = frontmatter.parse(read(item)).meta
        except (OSError, UnicodeDecodeError):
            return False
        return meta.get("type") == "moc" and bool(meta.get("template"))
    return project.enums_file.exists()


def _users(project: Project, rel: str) -> tuple[list[str], list[str]]:
    """Tracked files outside the documents root that spell this path: (programs that read it, places that link a document)."""
    outside = f":(exclude){project.rel(project.docs)}"
    spelled = re.compile(rf"(?<![\w-]){re.escape(rel)}(?![\w-])(.*)")
    programs, links = [], []
    for name in git_out(["grep", "-l", "-I", "-F", "-e", rel, "--", ".", outside], project.root).splitlines():
        try:
            text = nfc(read(project.root / name))
        except (OSError, UnicodeDecodeError):
            continue
        rests = [m.group(1) for line in text.split("\n") if (m := spelled.search(line))]
        if not rests:
            continue
        linked = Path(name).suffix.lower() in PROSE or all(_TO_DOCUMENT.search(rest) for rest in rests)
        (links if linked else programs).append(name)
    return programs, links


def adopt_plan(project: Project, source: Path | None = None) -> AdoptPlan:
    """Decide, item by item, what moves into `docs/5. 기존 문서/` and what stays. Changes nothing.

    An item stays when it is LanternSpec's own (told by a mark, not by its name), when lantern.yaml
    `docs.keep` lists it, when a tracked script · setting · code file outside the documents root
    reads its path (a path that leads to a document is a link, not a use), or when it is a GitHub
    Pages file. Everything else moves.

    Args:
        project: The project.
        source: One file or folder to move instead (it may be outside the documents root).

    Returns:
        The items with their reasons, the outside links that would break, and warnings.

    Raises:
        FileNotFoundError: source does not exist.

    Example:
        >>> [(i.path.name, i.move) for i in adopt_plan(project).items]  # doctest: +SKIP
        [('1. 기획', True), ('updates', False)]
    """
    legacy = project.folder("legacy")
    if source is not None:
        src = source if source.is_absolute() else project.root / source
        if not src.exists():
            raise FileNotFoundError(msg("Not found: {source}", source=source))
        return AdoptPlan([_unless_taken(project, AdoptItem(src, True, msg("chosen with --from")))])
    result = AdoptPlan()
    if not project.docs.exists():
        return result
    ours = _our_names(project)
    keep = {nfc(k).strip("/").split("/")[0] for k in project.profile.get("docs.keep") or []}
    docs_rel = project.rel(project.docs)
    for item in sorted(project.docs.iterdir()):
        name = nfc(item.name)
        if name.startswith(".") or item.resolve() == legacy.resolve():
            continue
        shown = f"{docs_rel}/{name}"
        if name in keep:
            result.items.append(AdoptItem(item, False, msg("listed in lantern.yaml docs.keep")))
        elif name in ours:
            if not _made_by_lantern(project, item):  # scaffold init makes ours at this path again, so links to it still work
                result.items.append(_unless_taken(project, AdoptItem(item, True, msg("same name, but not made by LanternSpec"))))
        elif name in PAGES_FILES:
            result.items.append(AdoptItem(item, False, msg("GitHub Pages file")))
        else:
            programs, links = _users(project, shown)
            if programs:
                more = msg(" (+{count} more)", count=len(programs) - 1) if len(programs) > 1 else ""
                result.items.append(AdoptItem(item, False, msg("{file} uses this path", file=programs[0]) + more))
                continue
            moved = _unless_taken(project, AdoptItem(item, True, msg("documents")))
            result.items.append(moved)
            if moved.move:
                result.links += [(u, shown + ("/" if item.is_dir() else "")) for u in links]
    cwd = project.docs_git_cwd()
    if git(["rev-parse", "--git-dir"], cwd).returncode == 0:
        untracked = [p for p in result.moves if not git_out(["ls-files", "--", str(p)], cwd)]
        if untracked:
            result.notes.append(
                msg(
                    "⚠ {count} of these are not tracked by git (ignored or never added) — they move as plain files, "
                    "with no commit for git revert to undo",
                    count=len(untracked),
                )
            )
    pages = [i.path.name for i in result.items if i.path.name in PAGES_FILES]
    if pages and result.moves:
        result.notes.append(
            msg(
                "⚠ {root}/ looks like a GitHub Pages site ({items}) — a page that moves gets a new address. "
                "List what must stay in lantern.yaml docs.keep",
                root=docs_rel,
                items=" · ".join(pages),
            )
        )
    return result


def _unless_taken(project: Project, item: AdoptItem) -> AdoptItem:
    """A move whose place in the legacy folder is taken stays, for a person to merge."""
    dest = project.folder("legacy") / item.path.name
    if dest.exists():
        return AdoptItem(item.path, False, msg("{rel} already exists — merge them by hand", rel=project.rel(dest)))
    return item


def describe(project: Project, result: AdoptPlan) -> list[str]:
    """Write a plan for the user.

    Args:
        project: The project.
        result: The plan.

    Returns:
        One line per item (move · keep, name, reason), then warnings and the outside links that would break.

    Example:
        >>> describe(project, adopt_plan(project))  # doctest: +SKIP
        ['옮김  1. 기획/  (문서)', '남김  updates/  (Scripts/release.sh가 이 경로를 씁니다)']
    """
    out = []
    for item in result.items:
        name = nfc(item.path.name) + ("/" if item.path.is_dir() else "")
        out.append(f"{msg('move') if item.move else msg('keep')}  {name}  ({item.reason})")
    out += result.notes
    if result.links:
        out.append(
            msg("🔗 {count} places outside the documents point at paths that move — fix them after the move:", count=len(result.links))
        )
        out += [f"   {source} → {target}" for source, target in result.links[:20]]
        if len(result.links) > 20:
            out.append(msg("   … and {count} more", count=len(result.links) - 20))
    return out


def adopt(project: Project, result: AdoptPlan) -> list[str]:
    """Carry out a plan: move with `git mv` (history continues), add the moved files to the map, then commit once.

    The documents' git must have nothing staged and no changes in what moves or in the documents
    root, so the commit holds only this move and one revert undoes it.

    Args:
        project: The project.
        result: The plan from adopt_plan().

    Returns:
        What was done.

    Raises:
        LegacyError: There are uncommitted changes, or nothing has ever been committed.

    Example:
        >>> adopt(project, adopt_plan(project))  # doctest: +SKIP
        ['✔ 3개를 docs/5. 기존 문서/로 옮겼습니다', '   커밋 하나 3f2a1c0 — 되돌리려면 git revert 3f2a1c0']
    """
    moves = result.moves
    if not moves:
        return []
    legacy = project.folder("legacy")
    cwd = project.docs_git_cwd()
    scope = [str(project.docs), *(str(p) for p in moves if project.docs.resolve() not in p.resolve().parents)]
    in_git = git(["rev-parse", "--git-dir"], cwd).returncode == 0
    if in_git:
        if git(["rev-parse", "--verify", "-q", "HEAD"], cwd).returncode != 0:
            raise LegacyError(msg("Nothing has been committed yet — commit once, then run lantern legacy adopt --apply again"))
        if git_out(["diff", "--cached", "--name-only"], cwd) or git_out(["status", "--porcelain", "--", *scope], cwd):
            raise LegacyError(msg("Commit or stash the changes in the documents first, then run lantern legacy adopt --apply again"))
    for src in moves:
        move_path(project, src, legacy / src.name)
    legacy.mkdir(parents=True, exist_ok=True)
    legacy_map = add_map_rows(project)
    out = [msg("✔ Moved {count} items to {rel}/", count=len(moves), rel=project.rel(legacy))]
    if in_git:
        if legacy_map:  # git mv staged the moves; only the map's new rows are added, never files git was told to ignore
            git(["add", "--", str(legacy_map)], cwd)
        if git(["diff", "--cached", "--quiet"], cwd).returncode == 0:  # git tracks none of it: nothing to commit
            return out
        r = git(["commit", "-q", "-m", msg("docs: move existing documents to the legacy folder [lantern]")], cwd, env=SKIP_HOOKS)
        if r.returncode == 0:
            out.append(msg("   one commit {sha} — git revert {sha} undoes it", sha=git_out(["rev-parse", "--short", "HEAD"], cwd)))
        else:
            out.append(msg("⚠ The move is staged but not committed — commit it yourself: {error}", error=r.stderr.strip()[:200]))
    return out


def legacy_files(project: Project) -> list[Path]:
    """List the files kept in the legacy folder (the map itself and hidden files left out).

    Args:
        project: The project.

    Returns:
        The files, sorted; empty when there is no legacy folder.

    Example:
        >>> [p.name for p in legacy_files(project)]  # doctest: +SKIP
        ['README.md', '설계 메모.md']
    """
    legacy = project.folder("legacy")
    if not legacy.exists():
        return []
    return sorted(
        p
        for p in legacy.rglob("*")
        if p.is_file()
        and nfc(p.name) != nfc(project.names.file("legacy_map"))
        and not any(x.startswith(".") for x in p.relative_to(legacy).parts)
    )


def map_rows(project: Project, files: list[Path]) -> str:
    """Build the map's table rows for legacy files, with blanks for the person to fill.

    Args:
        project: The project.
        files: Legacy files.

    Returns:
        One row per file; a single blank row when there are none.

    Example:
        >>> map_rows(project, []).count("|")  # doctest: +SKIP
        6
    """
    rows = []
    for p in files:
        rel = project.docs_rel(p)
        target = rel[:-3] if rel.endswith(".md") else rel
        rows.append(
            msg(
                "| [[{target}\\|{nfc}]] | {{{{What it says}}}} | {{{{Still true?}}}} | {{{{Absorb · Archive "
                "· Move}}}} | {{{{New place}}}} |",
                target=target,
                nfc=nfc(p.stem),
            )
        )
    return "\n".join(rows) or msg(
        "| {{{{Document}}}} | {{{{What it says}}}} | {{{{Still true?}}}} | {{{{Absorb · Archive · Move}}}} | {{{{New place}}}} |"
    )


def add_map_rows(project: Project) -> Path | None:
    """Add a row to the legacy map for every legacy file it does not mention yet.

    Args:
        project: The project.

    Returns:
        The map; None when there is no map.

    Example:
        >>> add_map_rows(project).name  # doctest: +SKIP
        '기존 문서 지도.md'
    """
    n = project.names
    legacy = project.folder("legacy")
    m = legacy / n.file("legacy_map")
    if not m.exists() or n.is_unused("legacy_docs"):
        return None if not m.exists() else m
    text = read(m)
    # a folder the map links as a whole (one row for everything in it) covers its files
    whole = [project.docs_rel(d) for d in legacy.iterdir() if d.is_dir() and f"[[{project.docs_rel(d)}\\|" in text]
    missing = [
        p
        for p in legacy_files(project)
        if project.docs_rel(p).rsplit(".", 1)[0] not in text and not any(project.docs_rel(p).startswith(w + "/") for w in whole)
    ]
    if not missing:
        return m
    section = sections.find(text, n.titles("legacy_docs"))
    if section is None:  # the person removed or renamed the section: check asks about it
        return m
    lines = section.group(2).split("\n")
    # drop the template's blank example row (every cell a {{blank}}) once real rows exist
    lines = [l for l in lines if not _blank_row(l)]
    last = max((i for i, l in enumerate(lines) if l.startswith("|")), default=-1)
    lines[last + 1 : last + 1] = map_rows(project, missing).split("\n")
    write(m, text[: section.start(2)] + "\n".join(lines) + text[section.end(2) :])
    return m


def _blank_row(line: str) -> bool:
    """A table row whose every cell is a {{blank}}."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
    return bool(cells) and all(re.fullmatch(r"\{\{[^{}]+\}\}", c) for c in cells)


def todos(project: Project) -> list[dict[str, str]]:
    """Find TODO-like lines in legacy text documents (TODO, FIXME, "나중에", open check boxes …).

    Args:
        project: The project.

    Returns:
        file (from the docs root), line and text for each match.

    Example:
        >>> todos(project)[0]["text"]  # doctest: +SKIP
        'TODO: 로그인 실패 처리'
    """
    out = []
    for p in legacy_files(project):
        if p.suffix.lower() not in (".md", ".txt", ".markdown"):
            continue
        for i, line in enumerate(read(p).split("\n"), start=1):
            s = line.strip()
            if s and TODO_RE.search(s) and not s.startswith("- [x]"):
                out.append({"file": project.docs_rel(p), "line": str(i), "text": s[:160]})
    return out
