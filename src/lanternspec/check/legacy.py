"""Existing documents of a brownfield project (I-02): originals stay in `5. 기존 문서/`; the script builds the map and TODOs."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..core.profile import FOLDERS, MOC_FILE
from ..core.project import Project, git, git_out, nfc, read, write

TODO_RE = re.compile(r"(TODO|FIXME|나중에|추후|언젠가|해야 할|할 것|아이디어|개선 필요|- \[ \])", re.I)


def _ours(project: Project) -> set:
    tops = {nfc(v.split("/")[0]) for v in FOLDERS.values()}
    return tops | {nfc(MOC_FILE), ".git", ".obsidian"}


def _move(project: Project, src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tracked = bool(git_out(["ls-files", "--", str(src)], project.root))
    if tracked:
        r = git(["mv", str(src), str(dest)], project.root)
        if r.returncode == 0:
            return
    shutil.move(str(src), str(dest))


def adopt(project: Project, source: Path | None = None) -> list[str]:
    """Move existing documents into `docs/5. 기존 문서/` (git mv keeps their history)."""
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
    legacy = project.folder("legacy")
    if not legacy.exists():
        return []
    return sorted(
        p
        for p in legacy.rglob("*")
        if p.is_file() and nfc(p.name) != "기존 문서 지도.md" and not any(x.startswith(".") for x in p.relative_to(legacy).parts)
    )


def map_rows(project: Project, files: list[Path]) -> str:
    rows = []
    for p in files:
        rel = project.docs_rel(p)
        target = rel[:-3] if rel.endswith(".md") else rel
        rows.append(
            f"| [[{target}\\|{nfc(p.stem)}]] | {{{{무슨 내용}}}} | {{{{아직 맞나}}}} | {{{{흡수 · 보관 · 옮기기}}}} | {{{{새 위치}}}} |"
        )
    return "\n".join(rows) or "| {{문서}} | {{무슨 내용}} | {{아직 맞나}} | {{흡수 · 보관 · 옮기기}} | {{새 위치}} |"


def add_map_rows(project: Project) -> Path | None:
    """Add a row for every legacy file the map does not mention yet."""
    m = project.folder("legacy") / "기존 문서 지도.md"
    if not m.exists():
        return None
    text = read(m)
    missing = [p for p in legacy_files(project) if project.docs_rel(p).rsplit(".", 1)[0] not in text]
    if not missing:
        return m
    rows = map_rows(project, missing)
    lines = text.split("\n")
    # drop the template's blank example row once real rows exist
    lines = [l for l in lines if l.strip() != "| {{문서}} | {{무슨 내용}} | {{아직 맞나}} | {{흡수 · 보관 · 옮기기}} | {{새 위치}} |"]
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "## 문서")
    except StopIteration:
        write(m, text.rstrip() + "\n\n## 문서\n| 문서 | 무슨 내용 | 아직 맞나 | 갈래 | 새 위치 |\n|---|---|---|---|---|\n" + rows + "\n")
        return m
    last = start
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("|"):
            last = i
        elif lines[i].startswith("## "):
            break
    lines[last + 1 : last + 1] = rows.split("\n")
    write(m, "\n".join(lines))
    return m


def todos(project: Project) -> list[dict[str, str]]:
    out = []
    for p in legacy_files(project):
        if p.suffix.lower() not in (".md", ".txt", ".markdown"):
            continue
        for i, line in enumerate(read(p).split("\n"), start=1):
            s = line.strip()
            if s and TODO_RE.search(s) and not s.startswith("- [x]"):
                out.append({"file": project.docs_rel(p), "line": str(i), "text": s[:160]})
    return out
