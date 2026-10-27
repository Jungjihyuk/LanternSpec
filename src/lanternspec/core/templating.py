"""Turn a template into a document.

Three kinds of marks live in a template:

* ``${name}``  — filled by the script (id, today, work link …). Never by the AI.
* ``{{name}}`` / ``{{name (필수)}}`` — blanks the AI (or a person) fills; ``(필수)`` marks a required one.
* ``<!-- lantern:if key=a,b -->`` … ``<!-- lantern:endif -->`` — kept only when the
  profile matches (I-04 client sections, AC format, team-only lines).

Everything after ``<!-- lantern:template-only -->`` (the change log) stays in the template.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from . import frontmatter

TEMPLATE_ONLY = "<!-- lantern:template-only -->"
_SYS_RE = re.compile(r"\$\{([a-z_]+(?:\.[a-z_]+)*)\}")
PLACEHOLDER_RE = re.compile(r"\{\{([^{}\n]+?)\}\}")
FORBIDDEN_FIELD_NAMES = {"date", "time", "title"}  # Obsidian core templates replace these (TE-01)


def _matches(cond: str, ctx: Mapping[str, Any]) -> bool:
    cond = cond.strip()
    negate = cond.startswith("!")
    if negate:
        cond = cond[1:].strip()
    if "=" in cond:
        key, raw = cond.split("=", 1)
        wanted = {v.strip() for v in raw.split(",") if v.strip()}
        val = ctx.get(key.strip())
        have = {str(v) for v in val} if isinstance(val, (list, tuple, set)) else {str(val)}
        result = bool(wanted & have)
    else:
        result = bool(ctx.get(cond))
    return not result if negate else result


_MARK_RE = re.compile(r"<!--\s*lantern:(if\s+[^>]*?|endif)\s*-->")


def apply_conditions(text: str, ctx: Mapping[str, Any]) -> str:
    """Resolve lantern:if blocks (nesting allowed). Works inline and across whole lines.

    A marker alone on its line takes its line break with it, so removed blocks leave no gap.
    """
    out: list[str] = []
    stack: list[bool] = []  # is each open block kept?
    pos = 0
    for m in _MARK_RE.finditer(text):
        if all(stack):
            out.append(text[pos : m.start()])
        line_start = m.start() == 0 or text[m.start() - 1] == "\n"
        line_end = text[m.end() : m.end() + 1] in ("\n", "")
        own_line = line_start and line_end
        token = m.group(1)
        if token.startswith("if"):
            stack.append(all(stack) and _matches(token[2:], ctx))
        elif stack:
            stack.pop()
        pos = m.end() + (1 if own_line and m.end() < len(text) else 0)
    if all(stack):
        out.append(text[pos:])
    result = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", result)


def strip_template_only(text: str) -> str:
    idx = text.find(TEMPLATE_ONLY)
    if idx == -1:
        return text
    return text[:idx].rstrip() + "\n"


def fill_system(text: str, values: Mapping[str, Any]) -> str:
    def rep(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in values:
            v = values[key]
            return "" if v is None else str(v)
        return m.group(0)

    return _SYS_RE.sub(rep, text)


def render(template_text: str, values: Mapping[str, Any], ctx: Mapping[str, Any] | None = None) -> str:
    """Template text -> new document text."""
    text = strip_template_only(template_text)
    text = apply_conditions(text, ctx or {})
    text = fill_system(text, values)
    # the copy no longer needs to know which base version the template came from
    doc = frontmatter.parse(text)
    if doc.has_frontmatter and "based_on" in doc.meta:
        text = frontmatter.set_fields(text, {"based_on": frontmatter.DELETE}, touch=False)
    return text


def placeholders(text: str) -> list[tuple[str, bool, int]]:
    """(name, required, line_no) for every {{…}} outside code fences."""
    # blanks inside mermaid/dbml fences count too — templates put them there on purpose
    out: list[tuple[str, bool, int]] = []
    for i, line in enumerate(text.split("\n"), start=1):
        for m in PLACEHOLDER_RE.finditer(line):
            name = m.group(1).strip()
            required = name.endswith("(필수)")
            out.append((name, required, i))
    return out


def field_base_name(name: str) -> str:
    return re.sub(r"\s*\(필수\)\s*$", "", name).strip()


def yaml_list(items: list[str]) -> str:
    """Inline YAML list for ${links}-style values."""
    if not items:
        return "[]"
    parts = []
    for it in items:
        s = str(it).replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'"{s}"')
    return "[" + ", ".join(parts) + "]"


def yaml_str(value: str | None) -> str:
    if value is None or value == "":
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'
