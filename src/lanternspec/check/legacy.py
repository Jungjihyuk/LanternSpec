"""Existing documents of a brownfield project: originals stay in `5. 기존 문서/`; the script builds the map and TODOs.

Not here:
    - deciding where each document's content goes — the person does that in the map (/l-init)
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..core import sections
from ..core.project import Project, git, git_out, nfc, read, write

TODO_RE = re.compile(r"(TODO|FIXME|나중에|추후|언젠가|해야 할|할 것|아이디어|개선 필요|- \[ \])", re.I)


def _ours(project: Project) -> set:
    tops = {nfc(v.split("/")[0]) for v in project.names.folders().values()}
    return tops | {nfc(project.names.file("moc")), ".git", ".obsidian"}


def _move(project: Project, src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tracked = bool(git_out(["ls-files", "--", str(src)], project.root))
    if tracked:
        r = git(["mv", str(src), str(dest)], project.root)
        if r.returncode == 0:
            return
    shutil.move(str(src), str(dest))


def adopt(project: Project, source: Path | None = None) -> list[str]:
    """Move existing documents into `docs/5. 기존 문서/` (git mv keeps their history) and add them to the map.

    Args:
        project: The project.
        source: A file or folder to move; when None, everything in the documents root that is not ours.

    Returns:
        Where each item moved, relative to the project root.

    Raises:
        FileNotFoundError: source does not exist.

    Example:
        >>> adopt(project, Path("wiki"))  # doctest: +SKIP
        ['docs/5. 기존 문서/wiki']
    """
    legacy = project.folder("legacy")
    moved: list[str] = []
    if source is None:
        if not project.docs.exists():
            return []
        ours = _ours(project)
        for item in sorted(project.docs.iterdir()):
            if nfc(item.name) in ours or item.name.startswith("."):
                continue
            dest = legacy / item.name
            _move(project, item, dest)
            moved.append(project.rel(dest))
    else:
        src = source if source.is_absolute() else project.root / source
        if not src.exists():
            raise FileNotFoundError(f"없습니다: {source}")
        dest = legacy / src.name
        _move(project, src, dest)
        moved.append(project.rel(dest))
    legacy.mkdir(parents=True, exist_ok=True)
    add_map_rows(project)
    return moved


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
            f"| [[{target}\\|{nfc(p.stem)}]] | {{{{무슨 내용}}}} | {{{{아직 맞나}}}} | {{{{흡수 · 보관 · 옮기기}}}} | {{{{새 위치}}}} |"
        )
    return "\n".join(rows) or "| {{문서}} | {{무슨 내용}} | {{아직 맞나}} | {{흡수 · 보관 · 옮기기}} | {{새 위치}} |"


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
    m = project.folder("legacy") / n.file("legacy_map")
    if not m.exists() or n.is_unused("legacy_docs"):
        return None if not m.exists() else m
    text = read(m)
    missing = [p for p in legacy_files(project) if project.docs_rel(p).rsplit(".", 1)[0] not in text]
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
