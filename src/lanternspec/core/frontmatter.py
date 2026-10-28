"""Read and edit YAML frontmatter without disturbing the rest of the file.

Responsibilities:
    - split a document into frontmatter and body, reporting broken YAML instead of raising
    - change, add or delete frontmatter keys while keeping other lines and comments as written
    - small converters for frontmatter values (as_list · as_str)

Not here:
    - which values a field may hold → core/enums.py (rules_for)
    - the `lantern meta` command → core/meta.py
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from .messages import msg

_FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_KEY_RE = re.compile(r"^([A-Za-z0-9_\-가-힣]+)\s*:")


@dataclass
class Doc:
    r"""A document split into frontmatter and body.

    Attributes:
        meta: The parsed frontmatter; empty when there is none or it is broken.
        body: Everything after the closing `---`.
        raw_meta: The frontmatter text as written; None when the document has none.
        error: Why the frontmatter could not be read; None when it was fine.
        body_offset: The 0-based line number where the body starts.

    Example:
        >>> doc = parse("---\ntype: idea\n---\n# 제목\n")
        >>> doc.meta, doc.body, doc.body_offset
        ({'type': 'idea'}, '# 제목\n', 3)
    """

    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    raw_meta: str | None = None
    error: str | None = None
    body_offset: int = 0  # line number (0-based) where the body starts

    @property
    def has_frontmatter(self) -> bool:
        """Whether the document starts with a `---` block (even a broken one)."""
        return self.raw_meta is not None


def parse(text: str) -> Doc:
    r"""Split a document into frontmatter and body.

    Args:
        text: The whole document.

    Returns:
        The split document. Broken YAML, or frontmatter that is not a mapping,
        gives an empty meta with error set — it never raises.

    Example:
        >>> parse("---\nstatus: 🆕 새것\n---\n본문").meta
        {'status': '🆕 새것'}
        >>> parse("---\n- a\n---\n").error
        'frontmatter가 키: 값 형태가 아닙니다'
        >>> parse("본문만").has_frontmatter
        False
    """
    m = _FM_RE.match(text)
    if not m:
        return Doc(meta={}, body=text, raw_meta=None)
    raw = m.group(1)
    body = text[m.end() :]
    offset = text[: m.end()].count("\n")
    try:
        meta = yaml.safe_load(raw) or {}
        if not isinstance(meta, dict):
            return Doc(meta={}, body=body, raw_meta=raw, error=msg("frontmatter is not in key: value form"), body_offset=offset)
    except yaml.YAMLError as e:  # pragma: no cover - message varies
        first = str(e).splitlines()[0] if str(e) else msg("YAML error")
        return Doc(meta={}, body=body, raw_meta=raw, error=msg("frontmatter YAML error: {first}", first=first), body_offset=offset)
    return Doc(meta=meta, body=body, raw_meta=raw, body_offset=offset)


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _dump_value(key: str, value: Any) -> str:
    """`key: value` — block style, but scalar lists stay inline (`links: ["[[a]]"]`), dates unquoted."""
    if isinstance(value, str) and _ISO_DATE.match(value):
        try:
            value = _dt.date.fromisoformat(value)
        except ValueError:
            pass
    if isinstance(value, list) and all(not isinstance(v, (dict, list)) for v in value):
        flow = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, width=10_000).strip()
        head = yaml.safe_dump({key: None}, allow_unicode=True).split(":")[0]
        return f"{head}: {flow}"
    dumped = yaml.safe_dump({key: value}, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10_000)
    return dumped.rstrip("\n")


def _blocks(raw: str) -> list[list[str]]:
    """Split frontmatter text into top-level key blocks (comments stick to the next key)."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in raw.split("\n"):
        if _KEY_RE.match(line) and current and any(_KEY_RE.match(x) for x in current):
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _block_key(block: list[str]) -> str | None:
    for line in block:
        m = _KEY_RE.match(line)
        if m:
            return m.group(1)
    return None


def set_fields(text: str, updates: dict[str, Any], *, touch: bool = True) -> str:
    r"""Replace or add frontmatter keys; every other line stays as written.

    Comments above a replaced key are kept. Pass DELETE as a value to remove a key.
    A document without frontmatter gets a new block with just the updates.

    Args:
        text: The whole document.
        updates: Key → new value (DELETE removes the key).
        touch: Also set `updated` to today when the document already has that key.

    Returns:
        The document with the new frontmatter.

    Example:
        >>> text = "---\n# 상태\nstatus: 새것\ntags: [a]\n---\n본문\n"
        >>> print(set_fields(text, {"status": "검토", "tags": DELETE}), end="")
        ---
        # 상태
        status: 검토
        ---
        본문
    """
    m = _FM_RE.match(text)
    updates = dict(updates)
    if m is None:
        meta = dict(updates)
        head = "\n".join(_dump_value(k, v) for k, v in meta.items())
        return f"---\n{head}\n---\n{text}"
    raw = m.group(1)
    blocks = _blocks(raw)
    if touch and "updated" not in updates and any(_block_key(b) == "updated" for b in blocks):
        updates["updated"] = _dt.date.today().isoformat()
    seen = set()
    out: list[str] = []
    for block in blocks:
        key = _block_key(block)
        if key is not None and key in updates:
            # keep comments that sit above the key; replace the key's own lines
            for line in block:
                if _KEY_RE.match(line):
                    break
                out.append(line)
            if updates[key] is not _DELETE:
                out.append(_dump_value(key, updates[key]))
            seen.add(key)
        else:
            out.extend(block)
    for key, value in updates.items():
        if key not in seen and value is not _DELETE:
            out.append(_dump_value(key, value))
    new_raw = "\n".join(out)
    return f"---\n{new_raw}\n---\n" + text[m.end() :]


class _Delete:
    def __repr__(self) -> str:  # pragma: no cover
        return "DELETE"


_DELETE = _Delete()
DELETE = _DELETE


def render(meta: dict[str, Any], body: str) -> str:
    r"""Build a document from a frontmatter mapping and a body.

    Dates are written unquoted and lists of plain values stay on one line.

    Args:
        meta: Frontmatter keys and values, in the order to write them.
        body: The text after the frontmatter.

    Returns:
        The whole document.

    Example:
        >>> print(render({"type": "debt", "links": ["[[a]]"], "created": "2026-10-28"}, "# D-001\n"), end="")
        ---
        type: debt
        links: ['[[a]]']
        created: 2026-10-28
        ---
        # D-001
    """
    head = "\n".join(_dump_value(k, v) for k, v in meta.items())
    return f"---\n{head}\n---\n{body}"


def as_list(value: Any) -> list[Any]:
    """Read a frontmatter value that may be one item or a list.

    Args:
        value: The raw value.

    Returns:
        A list: empty for None or "", the list itself, or the single value wrapped.

    Example:
        >>> as_list(None), as_list("a"), as_list(["a", "b"])
        ([], ['a'], ['a', 'b'])
    """
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_str(value: Any) -> str:
    """Read a frontmatter value as text (YAML turns `2026-10-28` into a date).

    Args:
        value: The raw value.

    Returns:
        "" for None, ISO text for dates, str() otherwise.

    Example:
        >>> import datetime
        >>> as_str(datetime.date(2026, 10, 28)), as_str(None), as_str(3)
        ('2026-10-28', '', '3')
    """
    if value is None:
        return ""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)
