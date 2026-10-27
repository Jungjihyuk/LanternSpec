"""`lantern meta get|set` — read · write one document's frontmatter, with enum checks (P1: scripts own the format)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import enums as enums_mod
from . import frontmatter
from . import profile as profile_mod
from .project import Project, read, write


def resolve_doc(project: Project, target: str) -> Path:
    p = Path(target)
    if p.is_absolute() and p.exists():
        return p
    for cand in (project.root / target, project.docs / target, Path.cwd() / target):
        if cand.exists():
            return cand
    found = project.find_by_id(target)
    if found:
        return found
    raise FileNotFoundError(f"문서를 찾지 못했습니다: {target}")


def parse_assignments(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"key=value 형식이어야 합니다: {item}")
        k, v = item.split("=", 1)
        val = profile_mod.parse_value(v)
        out[k.strip()] = "" if val is None else val
    return out


def meta_set(project: Project, target: str, items: list[str]) -> tuple[Path, dict[str, Any]]:
    path = resolve_doc(project, target)
    updates = parse_assignments(items)
    text = read(path)
    meta = frontmatter.parse(text).meta
    enums = enums_mod.load(project.enums_file)
    rules = enums.rules_for(str(updates.get("type") or meta.get("type") or ""))
    for k, v in updates.items():
        if k in rules and str(v) not in rules[k].values:
            raise ValueError(f"{k}: '{v}'는 {rules[k].label} 값이 아닙니다 (가능: {', '.join(rules[k].values)})")
    write(path, frontmatter.set_fields(text, updates))
    return path, updates


def meta_get(project: Project, target: str, key: str | None = None) -> Any:
    meta = frontmatter.parse(read(resolve_doc(project, target))).meta
    return meta.get(key) if key else meta


def rename_enum_value(project: Project, enum: str, old: str, new: str) -> list[Path]:
    """`lantern enums rename`: the name changes in enums.yaml, and every document that stores it follows.

    Code, skills and templates find values by role, so they need no edit (skills are re-rendered by install).
    """
    path = project.enums_file
    if not path.exists():
        raise FileNotFoundError(f"{project.rel(path)}이 없습니다 — lantern scaffold init 먼저")
    current = project.enums
    if enum not in current.enums:
        raise LookupError(f"enums.yaml에 '{enum}'이 없습니다 (가능: {', '.join(current.enums)})")
    if new in current[enum].values:
        raise ValueError(f"{enum}에 '{new}'이 이미 있습니다")
    text = enums_mod.rename_in_text(read(path), enum, old, new)
    write(path, text)
    project.reload_enums()
    changed: list[Path] = []
    for doc in sorted(project.docs.rglob("*.md")):
        if project.templates_dir in doc.parents:
            continue  # templates write ${role} tokens, not names
        body = read(doc)
        updates = enums_mod.doc_value_updates(project.enums, enum, frontmatter.parse(body).meta, old, new)
        if updates:
            write(doc, frontmatter.set_fields(body, updates, touch=False))
            changed.append(doc)
    return changed
