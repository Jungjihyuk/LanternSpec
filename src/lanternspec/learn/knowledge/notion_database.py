"""What a Notion database's properties are, and how the values of a new row are written for it.

Responsibilities:
    - list the properties a person's values can fill, with their choices
    - turn values into what Notion takes, refusing anything the database doesn't have (Notion itself would add a new choice)

Not here:
    - asking Notion for the database and making the row → learn/knowledge/notion.py

Everything here is a plain function of the database Notion described.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ...core.messages import msg
from ...core.project import nfc
from . import KnowledgeError, Property

_CHOICES = ("select", "status", "multi_select")
_TEXTS = ("url", "email", "phone_number")
FILLABLE = (*_CHOICES, *_TEXTS, "rich_text", "date", "number", "checkbox")  # others are computed or need an ID (people, relations, files)
_TRUE, _FALSE = ("true", "yes", "✔"), ("false", "no")


def title_property(database: dict[str, Any]) -> str:
    """Find the property that holds the title (every database has one, under a name of its own).

    Args:
        database: The database, as Notion describes it.

    Returns:
        The property's name.

    Example:
        >>> title_property({"properties": {"분류": {"type": "select"}, "제목": {"type": "title"}}})
        '제목'
    """
    return next((name for name, p in (database.get("properties") or {}).items() if p.get("type") == "title"), "title")


def fillable(database: dict[str, Any]) -> list[Property]:
    """List the properties a value can be given for: the title (the note's own) and computed ones are left out.

    Args:
        database: The database, as Notion describes it.

    Returns:
        The properties, in the order Notion gave them.

    Example:
        >>> fillable({"properties": {"제목": {"type": "title"}, "분류": {"type": "select", "select": {"options": [{"name": "개발"}]}}}})
        [Property(name='분류', kind='select', options=['개발'])]
    """
    return [
        Property(name, p["type"], [str(o.get("name")) for o in (p.get(p["type"]) or {}).get("options") or []])
        for name, p in (database.get("properties") or {}).items()
        if p.get("type") in FILLABLE
    ]


def _fold(text: str) -> str:
    return nfc(text).casefold().strip()


def _rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[i : i + 2000]}} for i in range(0, max(len(text), 1), 2000)] if text else []


def _choice(prop: Property, value: Any) -> dict[str, str]:
    """The choice a value names, whatever its case; a choice that isn't there is refused, not added."""
    for option in prop.options:
        if _fold(option) == _fold(str(value)):
            return {"name": option}
    raise KnowledgeError(
        msg("Property {name} has no choice '{value}' (choices: {options})", name=prop.name, value=value, options=", ".join(prop.options))
    )


def _number(value: Any) -> int | float:
    n = float(str(value))
    return int(n) if n.is_integer() else n


def _flag(value: Any) -> bool:
    text = _fold(str(value))
    if text not in (*_TRUE, *_FALSE):
        raise ValueError(text)
    return text in _TRUE


def _value(prop: Property, value: Any) -> dict[str, Any]:
    """One value, the way Notion takes it."""
    kind = prop.kind
    if kind == "multi_select":
        items = value if isinstance(value, list) else str(value).split(",")  # a choice's name can't hold a comma
        return {kind: [_choice(prop, item) for item in items if str(item).strip()]}
    try:
        if isinstance(value, list | dict):
            raise ValueError(value)
        if kind in _CHOICES:
            return {kind: _choice(prop, value)}
        if kind == "number":
            return {kind: _number(value)}
        if kind == "checkbox":
            return {kind: _flag(value)}
        if kind == "date":
            text = value.isoformat() if isinstance(value, date) else str(value).strip()
            datetime.fromisoformat(text)
            return {kind: {"start": text}}
    except (ValueError, OverflowError) as e:
        raise KnowledgeError(msg("Property {name} ({kind}) can't be '{value}'", name=prop.name, kind=kind, value=value)) from e
    if kind == "rich_text":
        return {kind: _rich(str(value))}
    return {kind: str(value).strip()}


def row_values(database: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Turn the values for a new row into Notion's form; empty values are left out.

    Args:
        database: The database, as Notion describes it.
        values: Property name → value (a list, or a comma list, for a property with several choices).

    Returns:
        Property name → Notion's value, without the title.

    Raises:
        KnowledgeError: The database has no such property or choice, the property can't be filled, or the value doesn't fit it.

    Example:
        >>> db = {"properties": {"유형": {"type": "multi_select", "multi_select": {"options": [{"name": "JWT"}, {"name": "보안"}]}}}}
        >>> row_values(db, {"유형": "jwt, 보안"})
        {'유형': {'multi_select': [{'name': 'JWT'}, {'name': '보안'}]}}
    """
    known = {_fold(p.name): p for p in fillable(database)}
    out: dict[str, Any] = {}
    for name, value in values.items():
        if value is None or value == "" or value == []:
            continue
        prop = known.get(_fold(str(name)))
        if prop is None:
            if _fold(str(name)) == _fold(title_property(database)):
                raise KnowledgeError(msg("Property {name} is the note's title: it is filled from the note's name", name=name))
            raise KnowledgeError(
                msg("No property '{name}' to fill (there are: {names})", name=name, names=", ".join(p.name for p in known.values()))
            )
        out[prop.name] = _value(prop, value)
    return out
