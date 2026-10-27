"""Read and edit YAML frontmatter without disturbing the rest of the file."""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_KEY_RE = re.compile(r"^([A-Za-z0-9_\-가-힣]+)\s*:")


@dataclass
class Doc:
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    raw_meta: str | None = None
    error: str | None = None
    body_offset: int = 0  # line number (0-based) where the body starts

    @property
    def has_frontmatter(self) -> bool:
        return self.raw_meta is not None


def parse(text: str) -> Doc:
    m = _FM_RE.match(text)
    if not m:
        return Doc(meta={}, body=text, raw_meta=None)
    raw = m.group(1)
    body = text[m.end() :]
    offset = text[: m.end()].count("\n")
    try:
        meta = yaml.safe_load(raw) or {}
        if not isinstance(meta, dict):
            return Doc(meta={}, body=body, raw_meta=raw, error="frontmatter가 키: 값 형태가 아닙니다", body_offset=offset)
    except yaml.YAMLError as e:  # pragma: no cover - message varies
        first = str(e).splitlines()[0] if str(e) else "YAML 오류"
        return Doc(meta={}, body=body, raw_meta=raw, error=f"frontmatter YAML 오류: {first}", body_offset=offset)
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
    """Return text with frontmatter keys replaced/added. Other lines stay as they were.

    ``touch`` refreshes ``updated`` when the document already tracks it.
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
    head = "\n".join(_dump_value(k, v) for k, v in meta.items())
    return f"---\n{head}\n---\n{body}"


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)
