"""`lantern meta get|set` — read and write one document's frontmatter, with enum checks.

Responsibilities:
    - find a document by path or ID
    - set frontmatter fields only to values allowed by enums.yaml
    - rename an enum value in enums.yaml and in every document that stores it

Not here:
    - editing frontmatter text → core/frontmatter.py
    - renaming the value inside enums.yaml text → core/enums.py (rename_in_text)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import enums as enums_mod
from . import frontmatter
from . import profile as profile_mod
from .project import Project, read, write


def resolve_doc(project: Project, target: str) -> Path:
    """Find a document from a path or an ID.

    Args:
        project: The project.
        target: An absolute path, a path from the project root, the documents root or the
            current folder, or a document ID such as "D-007".

    Returns:
        The document path.

    Raises:
        FileNotFoundError: Nothing matches.

    Example:
        >>> resolve_doc(project, "D-007").name  # doctest: +SKIP
        'D-007 JWT.md'
    """
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
    """Parse `key=value` arguments into frontmatter updates.

    Values are read like lantern.yaml values (numbers, booleans, lists); an empty value becomes "".

    Args:
        items: Arguments such as "status=해결" or "count=3".

    Returns:
        Key → parsed value.

    Raises:
        ValueError: An item has no "=".

    Example:
        >>> parse_assignments(["status=해결", "count=3", "note="])
        {'status': '해결', 'count': 3, 'note': ''}
    """
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"key=value 형식이어야 합니다: {item}")
        k, v = item.split("=", 1)
        val = profile_mod.parse_value(v)
        out[k.strip()] = "" if val is None else val
    return out


def meta_set(project: Project, target: str, items: list[str]) -> tuple[Path, dict[str, Any]]:
    """Set frontmatter fields of one document, refusing values enums.yaml does not allow.

    Args:
        project: The project.
        target: Path or ID of the document (see resolve_doc).
        items: `key=value` arguments.

    Returns:
        The document path and the updates written.

    Raises:
        FileNotFoundError: The document does not exist.
        ValueError: An item is malformed, or a value is not in its enum list.

    Example:
        >>> meta_set(project, "D-007", ["status=해결"])  # doctest: +SKIP
        (PosixPath('…/D-007 JWT.md'), {'status': '해결'})
    """
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
    """Read frontmatter of one document.

    Args:
        project: The project.
        target: Path or ID of the document (see resolve_doc).
        key: One key to read; all frontmatter when None.

    Returns:
        That key's value (None when absent), or the whole frontmatter mapping.

    Raises:
        FileNotFoundError: The document does not exist.

    Example:
        >>> meta_get(project, "D-007", "status")  # doctest: +SKIP
        '해결'
    """
    meta = frontmatter.parse(read(resolve_doc(project, target))).meta
    return meta.get(key) if key else meta


def rename_enum_value(project: Project, enum: str, old: str, new: str) -> list[Path]:
    """Rename an enum value in enums.yaml and in every document that stores it (`lantern enums rename`).

    Code, skills and templates find values by role, so they need no edit (skills are re-rendered by install).
    Templates are skipped because they hold `${role}` tokens, not names.

    Args:
        project: The project.
        enum: List name, e.g. "debt_status".
        old: Current name.
        new: New name.

    Returns:
        The documents that were changed.

    Raises:
        FileNotFoundError: The project has no enums.yaml yet.
        LookupError: The list or the old value does not exist.
        ValueError: The new name is already in the list.

    Example:
        >>> rename_enum_value(project, "debt_status", "되물음", "다시 물음")  # doctest: +SKIP
        [PosixPath('…/D-007 JWT.md')]
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
