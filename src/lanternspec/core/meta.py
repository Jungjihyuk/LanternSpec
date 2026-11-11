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

import re
from pathlib import Path
from typing import Any

from . import enums as enums_mod
from . import frontmatter
from . import profile as profile_mod
from .messages import msg
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
    raise FileNotFoundError(msg("Document not found: {target}", target=target))


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
            raise ValueError(msg("Must be key=value: {item}", item=item))
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
    enums = project.enums
    rules = enums.rules_for(str(updates.get("type") or meta.get("type") or ""))
    for k, v in updates.items():
        if k in rules and str(v) not in rules[k].values:
            raise ValueError(
                msg(
                    "{k}: '{v}' is not a {label} value (available: {items})",
                    k=k,
                    v=v,
                    label=rules[k].label,
                    items=", ".join(rules[k].values),
                )
            )
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


def add_missing_roles(project: Project) -> list[str]:
    """Add to the project's enums.yaml the values a newer version's code needs (`lantern upgrade`).

    A name the project already uses for something else is left alone; `lantern doctor` keeps reporting the role.

    Args:
        project: The project.

    Returns:
        One message per value added.

    Example:
        >>> add_missing_roles(project)  # doctest: +SKIP
        ["✔ enums.yaml idea_status: 🚧 막힘"]
    """
    path = project.enums_file
    if not path.exists():
        return []
    base = enums_mod.load(language=project.profile.language)
    current = project.enums
    text = read(path)
    out: list[str] = []
    for enum, roles in enums_mod.REQUIRED_ROLES.items():
        have = current.enums.get(enum)
        for role in roles:
            if have is None or role in have.roles or role not in base[enum].roles:
                continue
            name = base[enum].value(role)
            if name in have.values:
                continue
            text = enums_mod.add_value_in_text(text, enum, name, base[enum].icon(name), role)
            out.append(msg("✔ enums.yaml {enum}: {label}", enum=enum, label=base[enum].labelled(name)))
    if out:
        write(path, text)
        project.reload_enums()
    return out


def drop_legacy_sizes(project: Project) -> list[str]:
    """Remove the older size names (S · M · L) from the project's enums.yaml once nothing uses them.

    A name given a role (someone kept it on purpose) stays.

    Args:
        project: The project.

    Returns:
        A message when something was removed.

    Example:
        >>> drop_legacy_sizes(project)  # doctest: +SKIP
        ['✔ enums.yaml size: S · M · L 뺌']
    """
    from .taskfile import LEGACY_SIZES

    path = project.enums_file
    size = project.enums.get("size")
    if not path.exists() or size is None:
        return []
    gone = [name for name in LEGACY_SIZES if name in size.values and not size.role_of(name)]
    if not gone:
        return []
    text = read(path)
    block = re.search(r"^size:[ \t]*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if block is None:
        return []
    body = re.sub(r"^[ \t]+(" + "|".join(gone) + r"):[^\n]*\n", "", block.group(1), flags=re.M)
    write(path, text[: block.start(1)] + body + text[block.end(1) :])
    project.reload_enums()
    return [msg("✔ enums.yaml size: dropped {items}", items=" · ".join(gone))]


def previous_names(project: Project) -> list[tuple[str, str, str]]:
    """Find values the project still names the way lantern once shipped them, where today's default is different.

    enums.yaml lists them per value as `was:`. A name someone chose themselves is never listed, so it is never suggested.

    Args:
        project: The project.

    Returns:
        (list name, current name, today's name) for each one.

    Example:
        >>> previous_names(project)  # doctest: +SKIP
        [('size', '반나절', '4h'), ('size', '1d', '8h')]
    """
    if not project.enums_file.exists():
        return []
    base = enums_mod.load(language=project.profile.language)
    out = []
    for name, shipped in base.enums.items():
        mine = project.enums.get(name)
        if mine is None:
            continue
        for role, olds in shipped.previous.items():
            current, today_name = mine.roles.get(role, ""), shipped.roles.get(role, "")
            if current in olds and today_name and today_name not in mine.values:
                out.append((name, current, today_name))
    return out


def rename_previous_names(project: Project) -> list[str]:
    """Rename the values named the way lantern once shipped them to today's names, documents included (`lantern upgrade --apply`).

    Args:
        project: The project.

    Returns:
        One message per value renamed.

    Example:
        >>> rename_previous_names(project)  # doctest: +SKIP
        ['✔ enums.yaml size: 반나절 → 4h (문서 3개)']
    """
    out = []
    for name, old, new in previous_names(project):
        changed = rename_enum_value(project, name, old, new)
        out.append(msg("✔ enums.yaml {enum}: {old} → {new} ({count} documents)", enum=name, old=old, new=new, count=len(changed)))
    return out


def rename_enum_value(project: Project, enum: str, old: str, new: str) -> list[Path]:
    """Rename an enum value in enums.yaml and in every document that stores it (`lantern enums rename`).

    Code, skills and templates find values by role, so they need no edit (skills are re-rendered by install).
    A task size is stored on task lines (`[크기:: …]`), so those are renamed too.
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
        raise FileNotFoundError(msg("{rel} doesn't exist — run lantern scaffold init first", rel=project.rel(path)))
    current = project.enums
    if enum not in current.enums:
        raise LookupError(msg("enums.yaml has no '{enum}' (available: {items})", enum=enum, items=", ".join(current.enums)))
    if new in current[enum].values:
        raise ValueError(msg("{enum} already has '{new}'", enum=enum, new=new))
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
            body = frontmatter.set_fields(body, updates, touch=False)
        if enum == "size":
            body = _rename_task_sizes(project, body, old, new)
        if body != read(doc):
            write(doc, body)
            changed.append(doc)
    return changed


def _rename_task_sizes(project: Project, text: str, old: str, new: str) -> str:
    """Rename one size on the task lines of a document; other lines stay as they are."""
    from .taskfile import TASK_LINE, set_attr

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if TASK_LINE.match(line) and re.search(r"\[" + re.escape(project.names.attr("size")) + r"::\s*" + re.escape(old) + r"\s*\]", line):
            lines[i] = set_attr(line, "size", new, project.names)
    return "\n".join(lines)
